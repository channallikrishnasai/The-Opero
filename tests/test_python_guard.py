"""Startup guard: Python < 3.11 must be rejected with a clear, actionable message."""

import sys

import pytest

from core.python_guard import MIN_PYTHON, ensure_supported, version_error


def test_min_python_is_311() -> None:
    assert MIN_PYTHON == (3, 11)


def test_current_interpreter_is_supported() -> None:
    assert sys.version_info >= MIN_PYTHON
    ensure_supported()  # must not raise on the test interpreter


def test_rejects_python_310_with_clear_message() -> None:
    with pytest.raises(SystemExit) as excinfo:
        ensure_supported((3, 10, 11), r"C:\Python310\python.exe")
    message = str(excinfo.value)
    assert "3.11" in message
    assert "3.10.11" in message
    assert r"C:\Python310\python.exe" in message
    assert "Traceback" not in message


def test_accepts_supported_versions() -> None:
    ensure_supported((3, 11, 0), "python311")
    ensure_supported((3, 12, 10), "python312")
    ensure_supported((3, 13, 1), "python313")


def test_version_error_names_the_floor_and_the_running_version() -> None:
    message = version_error((3, 10, 11), "python")
    assert "Python 3.11+" in message
    assert "Python 3.10.11" in message
