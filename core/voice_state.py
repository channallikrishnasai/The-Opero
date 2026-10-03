"""Thread-safe voice state: the single gate between OPERO's speakers and its mic.

OPERO hears itself. When TTS audio reaches the microphone it comes back as a
"transcript", the model answers it, speaks again, and the loop feeds itself.
Every path that could carry that echo — Gemini-native mic streaming, Gemini
input transcriptions, AssemblyAI finals — passes this gate first:

    accept_mic / note_mic        while audio may be captured, and its generation
    accept_transcript            whether words arriving now are trustworthy
    begin_speaking/end_speaking  TTS boundaries
    interrupt                    user barge-in

Speech beginning bumps a generation counter; anything captured under an older
generation is stale by definition and rejected — that kills the loop even when
a transcript lands after the acoustic tail has expired.
"""

import threading
import time
from collections.abc import Callable
from enum import Enum

# Python 3.10 compatible StrEnum implementation
class StrEnum(str, Enum):
    """String enum base class for Python 3.10 compatibility."""
    pass


class VoiceState(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class VoiceGate:
    """One state machine shared by the Gemini-native and AssemblyAI paths."""

    def __init__(
        self,
        *,
        latency: float = 0.20,
        margin: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.latency = latency  # measured output latency, seconds (synced by _play_audio)
        self.margin = margin  # extra room-acoustic slack, seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._state = VoiceState.IDLE
        self._generation = 0
        self._mic_generation = 0  # generation the captured audio belongs to
        self._tail_until = 0.0

    @property
    def state(self) -> VoiceState:
        with self._lock:
            return self._state

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def in_tail(self) -> bool:
        """True while the speakers may still be finishing our last sentence."""
        with self._lock:
            return self._clock() < self._tail_until

    def clear_tail(self) -> None:
        """A verified human voice ends the acoustic tail early."""
        with self._lock:
            self._tail_until = 0.0

    def accept_mic(self) -> bool:
        """Mic audio may be captured unless we are speaking right now."""
        with self._lock:
            return self._state is not VoiceState.SPEAKING

    def note_mic(self) -> int:
        """Record that mic audio was captured; returns the generation it belongs to."""
        with self._lock:
            self._mic_generation = self._generation
            if self._state is VoiceState.IDLE:
                self._state = VoiceState.LISTENING
            return self._generation

    def accept_transcript(self) -> bool:
        """Whether words arriving now are trustworthy.

        Rejected while TTS plays, during the acoustic tail, or when the words
        derive from audio captured under an older generation — a stale
        AssemblyAI final or a late Gemini input transcription.
        """
        with self._lock:
            if self._state is VoiceState.SPEAKING:
                return False
            if self._clock() < self._tail_until:
                return False
            if self._mic_generation != self._generation:
                return False
            self._state = VoiceState.THINKING
            return True

    def begin_speaking(self) -> int:
        """TTS starts: invalidate everything captured before it.

        Idempotent — the playback loop calls this per chunk and a repeated
        call must not churn the generation counter.
        """
        with self._lock:
            if self._state is VoiceState.SPEAKING:
                return self._generation
            self._generation += 1
            self._state = VoiceState.SPEAKING
            self._tail_until = 0.0
            return self._generation

    def end_speaking(self) -> int:
        """TTS ends: listen again, but hold the acoustic tail open.

        `stream.write()` returns when the buffer accepts the audio, not when
        the speakers finish it, so echo keeps arriving for latency + margin.
        The mic is NOT muted during the tail — EchoGuard still lets a genuine
        instant reply through — but transcripts are not trusted inside it.
        """
        with self._lock:
            if self._state is VoiceState.SPEAKING:
                self._state = VoiceState.LISTENING
            self._tail_until = self._clock() + self.latency + self.margin
            return self._generation

    def interrupt(self) -> int:
        """Barge-in: drop the in-flight turn and reopen the room."""
        with self._lock:
            if self._state in (VoiceState.SPEAKING, VoiceState.THINKING):
                self._generation += 1
            if self._state is not VoiceState.IDLE:
                self._state = VoiceState.LISTENING
            self._tail_until = self._clock() + self.latency + self.margin
            return self._generation
