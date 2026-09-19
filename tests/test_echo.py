"""Tests for core.echo — echo cancellation / voice detection."""
import numpy as np
import pytest


def test_band_energies_basic():
    """band_energies returns an array of correct length."""
    from core.echo import band_energies, _BAND_EDGES

    pcm = np.random.randn(4800).astype(np.float32)
    energies = band_energies(pcm, sr=16000)
    assert isinstance(energies, np.ndarray)
    assert len(energies) == len(_BAND_EDGES) - 1


def test_band_energies_silence():
    """Near-silence produces very small energies."""
    from core.echo import band_energies

    pcm = np.zeros(4800, dtype=np.float32)
    energies = band_energies(pcm, sr=16000)
    assert energies.sum() < 1e-6


def test_band_energies_short_signal():
    """Very short signal returns zeros without crashing."""
    from core.echo import band_energies

    pcm = np.array([0.1, 0.2], dtype=np.float32)
    energies = band_energies(pcm, sr=16000)
    assert len(energies) == 8
    assert energies.sum() == 0.0


def test_echo_guard_initial_state():
    """EchoGuard starts uncalibrated with sensible defaults."""
    from core.echo import EchoGuard

    eg = EchoGuard()
    assert eg.calibrated is False
    assert eg.gain > 0
    assert eg.floor >= 0
    assert eg.threshold > 0


def test_echo_guard_no_history_passes_speech():
    """With no output history, any audible mic block is treated as speech."""
    from core.echo import EchoGuard

    eg = EchoGuard()
    pcm = np.random.randn(4800).astype(np.float32) * 0.5
    result = eg.is_user_speech(pcm, sr=16000, level=0.3)
    assert result is True


def test_echo_guard_low_level_not_speech():
    """Below _MIN_LEVEL the mic block is never called speech."""
    from core.echo import EchoGuard

    eg = EchoGuard()
    pcm = np.random.randn(4800).astype(np.float32) * 0.001
    result = eg.is_user_speech(pcm, sr=16000, level=0.01)
    assert result is False


def test_echo_guard_note_output_stores_history():
    """note_output() adds to the internal history."""
    from core.echo import EchoGuard

    eg = EchoGuard()
    pcm = np.random.randn(4800).astype(np.float32) * 0.5
    eg.note_output(pcm, sr=16000, level=0.5)
    assert len(eg._hist) == 1


def test_echo_guard_reset_clears_history():
    """reset() empties history but keeps learned state."""
    from core.echo import EchoGuard

    eg = EchoGuard()
    pcm = np.random.randn(4800).astype(np.float32) * 0.5
    eg.note_output(pcm, sr=16000, level=0.5)
    eg.reset()
    assert len(eg._hist) == 0


def test_echo_guard_requires_blocks_default():
    """required_blocks returns the noisy-block count when unreliable."""
    from core.echo import EchoGuard, _BLOCKS_NOISY

    eg = EchoGuard()
    # Initially floor is low so reliable=True
    assert eg.required_blocks in (5, 12)


def test_echo_guard_reliable_property():
    """reliable returns True when floor is below the unreliable threshold."""
    from core.echo import EchoGuard, _UNRELIABLE_FLOOR

    eg = EchoGuard()
    assert eg.floor < _UNRELIABLE_FLOOR
    assert eg.reliable is True
