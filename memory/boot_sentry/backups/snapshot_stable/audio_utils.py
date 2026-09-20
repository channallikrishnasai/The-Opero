"""Pure audio utility functions for PCM level analysis and viseme extraction."""

import numpy as np

# RMS below which 16-bit PCM is treated as room silence; above _LEVEL_FULL it
# reads as a full-height waveform.
_LEVEL_FLOOR = 60.0
_LEVEL_FULL  = 2600.0

# Viseme extraction parameters
_TAIL_MARGIN = 0.25
_VIS_WIN = 1024
_VIS_HOP = 480
_FIRST_SOUND_SAMPLES = 1024   # CHUNK_SIZE; imported from config at use time
_CURSOR_SLACK = 0.15


def pcm_level(samples) -> float:
    """Map a block of int16 PCM samples to a 0.0-1.0 loudness level.

    Returns 0.0 on empty/invalid input so it can never raise.
    """
    try:
        x = np.asarray(samples, dtype=np.float32)
        if x.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(x * x)))
    except Exception:
        return 0.0
    if rms <= _LEVEL_FLOOR:
        return 0.0
    return min(1.0, (rms - _LEVEL_FLOOR) / (_LEVEL_FULL - _LEVEL_FLOOR))


def pcm_visemes(samples, sr: int = 24000):
    """Slice a PCM block into (level, openness, width) frames, one per 20 ms.

    Returns [] on anything unexpected.
    """
    try:
        x = np.asarray(samples, dtype=np.float32)
        if x.size < _VIS_WIN:
            return []
        win = np.hanning(_VIS_WIN).astype(np.float32)
        freqs = np.fft.rfftfreq(_VIS_WIN, 1.0 / sr)
        b_f1_lo = (freqs >= 150) & (freqs < 450)
        b_f1_hi = (freqs >= 450) & (freqs < 1100)
        b_f2_bk = (freqs >= 600) & (freqs < 1300)
        b_f2_fr = (freqs >= 1700) & (freqs < 3200)
        b_hiss = (freqs >= 3800) & (freqs < 8000)

        out = []
        for start in range(0, x.size, _VIS_HOP):
            level = pcm_level(x[start:start + _VIS_HOP])
            seg = x[start:start + _VIS_WIN]
            if seg.size < _VIS_WIN:
                seg = np.concatenate([seg, np.zeros(_VIS_WIN - seg.size,
                                                    dtype=np.float32)])
            if level <= 0.0:
                out.append((0.0, 0.0, 0.0))
                continue
            mag = np.abs(np.fft.rfft((seg - seg.mean()) * win))
            f1l, f1h = float(mag[b_f1_lo].sum()), float(mag[b_f1_hi].sum())
            f2b, f2f = float(mag[b_f2_bk].sum()), float(mag[b_f2_fr].sum())
            hiss = float(mag[b_hiss].sum())

            openness = f1h / (f1l + f1h + 1e-6)
            width = (f2f - f2b) / (f2f + f2b + 1e-6)
            width *= (1.0 - openness) ** 0.8
            h = hiss / (f1l + f1h + f2b + f2f + hiss + 1e-6)
            openness *= 1.0 - 0.65 * min(1.0, h * 2.5)
            out.append((level,
                        float(min(1.0, max(0.0, openness))),
                        float(min(1.0, max(-1.0, width)))))
        return out
    except Exception:
        return []
