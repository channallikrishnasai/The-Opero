"""Tests for VoiceGate — the TTS self-hearing loop guard (no audio devices, no model)."""

from core.voice_state import VoiceGate, VoiceState


class _Clock:
    """Deterministic monotonic clock so the acoustic tail is testable."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _gate() -> tuple[VoiceGate, _Clock]:
    clock = _Clock()
    return VoiceGate(latency=0.2, margin=0.25, clock=clock), clock


def test_mic_rejected_during_tts() -> None:
    gate, _ = _gate()
    assert gate.accept_mic()
    gate.note_mic()
    gate.begin_speaking()
    assert gate.state is VoiceState.SPEAKING
    assert not gate.accept_mic()
    gate.end_speaking()
    assert gate.state is VoiceState.LISTENING
    assert gate.accept_mic()


def test_transcript_rejected_during_tts() -> None:
    gate, _ = _gate()
    gate.note_mic()
    gate.begin_speaking()
    assert not gate.accept_transcript()


def test_stale_transcript_rejected_after_tts() -> None:
    gate, clock = _gate()
    assert gate.accept_mic()
    gate.note_mic()  # audio captured under generation 0
    gate.begin_speaking()  # our own speech: generation 1
    gate.end_speaking()
    clock.advance(5.0)  # acoustic tail long expired
    assert not gate.accept_transcript()  # final from pre-TTS audio is still stale
    # A fresh utterance is accepted again once its audio is noted.
    assert gate.accept_mic()
    gate.note_mic()
    assert gate.accept_transcript()


def test_acoustic_tail() -> None:
    gate, clock = _gate()
    gate.begin_speaking()
    gate.end_speaking()
    assert gate.in_tail()
    # The mic stays open through the tail — only trust in words is withheld.
    assert gate.accept_mic()
    gate.note_mic()  # a real voice, passed by EchoGuard
    assert not gate.accept_transcript()
    clock.advance(0.44)
    assert gate.in_tail()
    assert not gate.accept_transcript()
    clock.advance(0.02)  # > latency (0.2) + margin (0.25)
    assert not gate.in_tail()
    assert gate.accept_transcript()


def test_interrupt() -> None:
    gate, clock = _gate()
    gate.note_mic()
    gate.begin_speaking()
    assert not gate.accept_mic()
    before = gate.generation
    gate.interrupt()
    assert gate.state is VoiceState.LISTENING
    assert gate.accept_mic()  # mic reopens immediately
    assert gate.generation > before  # in-flight turn invalidated
    assert not gate.accept_transcript()  # acoustic tail still guards the room
    clock.advance(1.0)
    assert not gate.accept_transcript()  # still stale until fresh audio is noted
    gate.note_mic()
    assert gate.accept_transcript()


def test_repeated_user_opero_user_cycles() -> None:
    gate, clock = _gate()
    assert gate.state is VoiceState.IDLE
    for _ in range(3):
        assert gate.accept_mic()
        gate.note_mic()
        assert gate.accept_transcript()
        assert gate.state is VoiceState.THINKING
        gate.begin_speaking()
        assert not gate.accept_mic()
        assert not gate.accept_transcript()
        gate.end_speaking()
        clock.advance(1.0)  # tail expires between turns
    # Each turn's own final, arriving late, never re-enters as user speech.
    assert not gate.accept_transcript()
