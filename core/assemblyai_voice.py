"""AssemblyAI streaming input adapter for OPERO.

This module owns only AssemblyAI transcription and its microphone stream.
Gemini Live remains connected in ``main.OperaLive`` and owns the assistant
turn, tools, output audio, and TTS.
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Callable

import sounddevice as sd

from core import audio_devices
from memory.config_manager import get_assemblyai_key, get_input_device

SAMPLE_RATE = 16_000
CHANNELS = 1
CHUNK_SIZE = 1024


class AssemblyAIVoice:
    """The one active microphone provider while AssemblyAI is selected."""

    def __init__(self, opero, generation: int, on_final: Callable[[str, int], None]):
        self._opero = opero
        self._generation = generation
        self._on_final = on_final
        self._running = False
        self._stopped = threading.Event()
        self._closed = False
        self._close_lock = threading.Lock()
        self._failure_reported = False
        self._failure_lock = threading.Lock()
        # A redelivered final arrives immediately with the same text. Keeping a
        # tiny, per-provider window rejects that transport duplicate without
        # treating a later, deliberate repeated command as the same turn.
        self._recent_finals: dict[str, float] = {}
        self._transcriber = None
        self._mic_stream = None

    @staticmethod
    def validate_configuration() -> str | None:
        if not get_assemblyai_key():
            return "AssemblyAI API key is missing. Add it in Configure before switching."
        try:
            import assemblyai as aai
        except ImportError:
            return "AssemblyAI support is not installed. Run pip install -r requirements.txt."
        if not hasattr(aai, "RealtimeTranscriber") or not hasattr(aai, "RealtimeFinalTranscript"):
            return "Installed AssemblyAI package is incompatible. Run pip install -r requirements.txt."
        return None

    async def run(self) -> None:
        """Connect and hold the input stream until the session is cancelled."""
        error = self.validate_configuration()
        if error:
            raise RuntimeError(error)

        import assemblyai as aai
        loop = asyncio.get_running_loop()

        def report_failure(message: str) -> None:
            with self._failure_lock:
                if self._failure_reported or self._stopped.is_set():
                    return
                self._failure_reported = True
            loop.call_soon_threadsafe(
                self._opero._on_assemblyai_error, self._generation, message,
            )

        def on_data(transcript) -> None:
            if not self._running or self._stopped.is_set():
                return
            text = (getattr(transcript, "text", "") or "").strip()
            if not text:
                return
            # Partials must never execute a command. AssemblyAI's explicit
            # final event alone enters OPERO's normal text command route.
            if (isinstance(transcript, aai.RealtimeFinalTranscript)
                    and self._accept_final(text)):
                loop.call_soon_threadsafe(self._on_final, text, self._generation)

        def on_error(error) -> None:
            if self._running and not self._stopped.is_set():
                print(f"[AssemblyAI] Streaming error: {type(error).__name__}")
                report_failure("AssemblyAI streaming connection failed.")

        def on_close() -> None:
            if self._running and not self._stopped.is_set():
                report_failure("AssemblyAI streaming connection closed unexpectedly.")

        self._transcriber = aai.RealtimeTranscriber(
            token=get_assemblyai_key(), sample_rate=SAMPLE_RATE,
            on_data=on_data, on_error=on_error, on_close=on_close,
        )
        self._running = True
        try:
            # OperaLive runs on the app's worker thread, not the UI thread.
            # Keep connect/close on that same thread so cancellation cannot
            # race a background connect against a concurrent close.
            self._transcriber.connect()
            if self._stopped.is_set():
                return
            self._open_microphone()
            self._opero.ui.write_log("SYS: AssemblyAI listening.")
            while not self._stopped.is_set():
                await asyncio.sleep(0.1)
        finally:
            self.stop()

    def _accept_final(self, text: str) -> bool:
        """Accept one final event, not its immediate websocket redelivery."""
        normalized = " ".join(text.casefold().split())
        now = time.monotonic()
        # Final events are normally emitted once; 1 second only covers an
        # immediate duplicate. A real second utterance is allowed afterwards.
        self._recent_finals = {
            key: seen for key, seen in self._recent_finals.items()
            if now - seen < 1.0
        }
        if normalized in self._recent_finals:
            return False
        self._recent_finals[normalized] = now
        return True

    def _open_microphone(self) -> None:
        def callback(indata, frames, time_info, status) -> None:
            if self._running and not self._stopped.is_set():
                self._opero._accept_assemblyai_audio(indata, self._send_audio)

        device = audio_devices.resolve(get_input_device(), "input")
        self._mic_stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16",
            blocksize=CHUNK_SIZE, device=device, callback=callback,
        )
        self._mic_stream.start()

    def _send_audio(self, data: bytes) -> None:
        if self._running and self._transcriber is not None:
            try:
                self._transcriber.send_audio(data)
            except Exception:
                # The SDK reports transport failures through on_error; never
                # let a sounddevice callback terminate the audio thread.
                pass

    def _close_microphone(self) -> None:
        if self._mic_stream is not None:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

    def request_stop(self) -> None:
        """Non-blocking stop request safe to make from the settings UI thread."""
        self._stopped.set()
        self._running = False

    def stop(self) -> None:
        """Idempotently release mic and websocket before another provider starts."""
        with self._close_lock:
            if self._closed:
                return
            self.request_stop()
            self._close_microphone()
            if self._transcriber is not None:
                try:
                    self._transcriber.close()
                except Exception:
                    pass
                self._transcriber = None
            self._closed = True
