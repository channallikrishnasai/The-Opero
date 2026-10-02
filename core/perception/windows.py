"""Structured window awareness — observation only.

Reads the foreground window and the open-window list; never focuses, moves,
closes, or otherwise manipulates a window.
"""

import ctypes
import sys
from dataclasses import dataclass
from typing import Any

from .errors import PerceptionUnavailableError


@dataclass(frozen=True)
class WindowInfo:
    title: str
    process: str
    pid: int

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "process": self.process, "pid": self.pid}


def _user32():
    if sys.platform != "win32":
        raise PerceptionUnavailableError("window awareness is only implemented on Windows")
    return ctypes.windll.user32


def _window_text(user32, hwnd) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _window_pid(user32, hwnd) -> int:
    pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _enumerate_raw() -> list[tuple[str, int]]:
    user32 = _user32()
    found: list[tuple[str, int]] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def _visit(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            title = _window_text(user32, hwnd)
            if title.strip():
                found.append((title, _window_pid(user32, hwnd)))
        return True

    user32.EnumWindows(callback_type(_visit), 0)
    return found


def _active_raw() -> tuple[str, int] | None:
    user32 = _user32()
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    return (_window_text(user32, hwnd), _window_pid(user32, hwnd))


def _process_name(pid: int) -> str:
    if pid <= 0:
        return ""
    try:
        import psutil
    except ImportError:
        return ""
    try:
        return psutil.Process(pid).name()
    except Exception:  # process may have exited or be access-protected
        return ""


def get_open_windows() -> list[WindowInfo]:
    """Visible windows with a non-empty title, in z-order."""
    return [WindowInfo(title=title, process=_process_name(pid), pid=pid) for title, pid in _enumerate_raw()]


def get_active_window() -> WindowInfo | None:
    """Foreground window info, or None when there is no foreground window."""
    raw = _active_raw()
    if raw is None:
        return None
    title, pid = raw
    return WindowInfo(title=title, process=_process_name(pid), pid=pid)
