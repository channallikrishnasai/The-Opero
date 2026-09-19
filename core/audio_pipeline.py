"""Audio I/O pipeline: manages sounddevice mic/speaker stream lifecycle.

Extracted from OperaLive to separate hardware stream management from
session-level business logic (wake word, echo guard, PTT, etc.).
"""

import asyncio

import sounddevice as sd

from core.logger import get_logger
from core.config_utils import CHANNELS, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE, CHUNK_SIZE

log = get_logger(__name__)


class AudioPipeline:
    """Manages microphone input and speaker output streams.

    The callback logic (wake word gating, echo guard, PTT) is injected by
    the caller — this class only owns the hardware lifecycle.
    """

    def __init__(self):
        self._mic_stream = None
        self._speaker_stream = None
        self._muted = False

    # ── Microphone ────────────────────────────────────────────────────────

    def open_mic(self, callback, device=None, samplerate=SEND_SAMPLE_RATE,
                 channels=CHANNELS, blocksize=CHUNK_SIZE):
        """Open the mic stream.  Falls back to default if *device* fails."""
        from core import audio_devices

        def _open(dev):
            return sd.InputStream(
                samplerate=samplerate,
                channels=channels,
                dtype="int16",
                blocksize=blocksize,
                device=dev,
                callback=callback,
            )

        try:
            self._mic_stream = _open(device)
        except Exception as e:
            if device is None:
                raise
            log.warning("Mic device %r failed: %s — using default", device, e)
            self._mic_stream = _open(None)
        return self._mic_stream

    def close_mic(self):
        """Close the mic stream if open."""
        s = self._mic_stream
        self._mic_stream = None
        if s is not None:
            try:
                s.stop()
                s.close()
            except Exception:
                pass

    # ── Speaker ───────────────────────────────────────────────────────────

    def open_speaker(self, device=None, samplerate=RECEIVE_SAMPLE_RATE,
                     channels=CHANNELS, blocksize=CHUNK_SIZE):
        """Open the speaker stream.  Falls back to default if *device* fails."""
        def _open(dev):
            st = sd.RawOutputStream(
                samplerate=samplerate,
                channels=channels,
                dtype="int16",
                blocksize=blocksize,
                device=dev,
            )
            st.start()
            return st

        try:
            self._speaker_stream = _open(device)
        except Exception as e:
            if device is None:
                raise
            log.warning("Speaker device %r failed: %s — using default", device, e)
            self._speaker_stream = _open(None)
        return self._speaker_stream

    def close_speaker(self):
        """Close the speaker stream if open."""
        s = self._speaker_stream
        self._speaker_stream = None
        if s is not None:
            try:
                s.stop()
                s.close()
            except Exception:
                pass

    # ── Mute control ──────────────────────────────────────────────────────

    def set_muted(self, muted: bool):
        self._muted = muted

    @property
    def is_muted(self):
        return self._muted
