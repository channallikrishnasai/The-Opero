"""Structured window awareness — observation only.

Reads the foreground window, the open-window list, window geometry/state,
monitors and the cursor position; never focuses, moves, closes, or otherwise
manipulates a window. Every field degrades to None/"unknown" when the OS does
not report it — unknown is never presented as fact.
"""

import ctypes
import sys
import ctypes.wintypes
from dataclasses import dataclass
from typing import Any

from .errors import PerceptionUnavailableError


@dataclass(frozen=True)
class WindowInfo:
    title: str
    process: str
    pid: int
    # left, top, right, bottom in screen pixels — None when unavailable
    rect: tuple[int, int, int, int] | None = None
    # normal | minimized | maximized | unknown
    state: str = "unknown"
    hwnd: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "process": self.process, "pid": self.pid,
                "rect": self.rect, "state": self.state}


@dataclass(frozen=True)
class MonitorInfo:
    index: int
    rect: tuple[int, int, int, int]
    primary: bool

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "rect": self.rect, "primary": self.primary}


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


def _window_rect(user32, hwnd) -> tuple[int, int, int, int] | None:
    try:
        r = ctypes.wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return (int(r.left), int(r.top), int(r.right), int(r.bottom))
    except Exception:
        pass
    return None


def _window_state(user32, hwnd) -> str:
    try:
        if user32.IsIconic(hwnd):
            return "minimized"
        if user32.IsZoomed(hwnd):
            return "maximized"
        return "normal"
    except Exception:
        return "unknown"


def _enumerate_raw() -> list[tuple[str, int, int]]:
    user32 = _user32()
    found: list[tuple[str, int, int]] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def _visit(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            title = _window_text(user32, hwnd)
            if title.strip():
                found.append((title, _window_pid(user32, hwnd), int(hwnd)))
        return True

    user32.EnumWindows(callback_type(_visit), 0)
    return found


def _active_raw() -> tuple[str, int, int] | None:
    user32 = _user32()
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    return (_window_text(user32, hwnd), _window_pid(user32, hwnd), int(hwnd))


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
    """Visible windows with a non-empty title, in z-order (first = topmost)."""
    user32 = _user32()
    return [
        WindowInfo(title=title, process=_process_name(pid), pid=pid,
                   rect=_window_rect(user32, hwnd),
                   state=_window_state(user32, hwnd), hwnd=hwnd)
        for title, pid, hwnd in _enumerate_raw()
    ]


def get_active_window() -> WindowInfo | None:
    """Foreground window info, or None when there is no foreground window."""
    raw = _active_raw()
    if raw is None:
        return None
    title, pid, hwnd = raw
    user32 = _user32()
    return WindowInfo(title=title, process=_process_name(pid), pid=pid,
                      rect=_window_rect(user32, hwnd),
                      state=_window_state(user32, hwnd), hwnd=hwnd)


def get_monitors() -> list[MonitorInfo]:
    """All attached monitors with pixel rects; index 0 first."""
    if sys.platform != "win32":
        raise PerceptionUnavailableError("monitor enumeration is only implemented on Windows")
    monitors: list[MonitorInfo] = []
    try:
        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.POINTER(ctypes.wintypes.RECT), ctypes.c_void_p)

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.wintypes.DWORD),
                        ("rcMonitor", ctypes.wintypes.RECT),
                        ("rcWork", ctypes.wintypes.RECT),
                        ("dwFlags", ctypes.wintypes.DWORD)]

        def _visit(hmonitor, _hdc, lprect, _lparam):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            rect = (int(lprect.contents.left), int(lprect.contents.top),
                    int(lprect.contents.right), int(lprect.contents.bottom))
            primary = False
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                primary = bool(info.dwFlags & 1)  # MONITORINFOF_PRIMARY
            monitors.append(MonitorInfo(index=len(monitors), rect=rect, primary=primary))
            return True

        user32.EnumDisplayMonitors(None, None, callback_type(_visit), 0)
    except Exception:
        pass
    if not monitors:
        # Single-monitor fallback: never invent bounds we did not read.
        try:
            w, h = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
            monitors.append(MonitorInfo(index=0, rect=(0, 0, int(w), int(h)), primary=True))
        except Exception:
            return []
    return monitors


def get_cursor_pos() -> tuple[int, int] | None:
    """Current cursor position in screen pixels, or None when unavailable."""
    try:
        if sys.platform != "win32":
            return None
        pt = ctypes.wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            return (int(pt.x), int(pt.y))
    except Exception:
        pass
    return None
