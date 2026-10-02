"""Desktop perception: observation of screen, windows, and browser state.

Observation only. Nothing in this package performs actions, focuses or closes
windows, drives a browser, or sends captures anywhere — captures are produced
explicitly on call and are never auto-forwarded to Gemini. Browser/app control
stays in the action engine behind its existing confirmation gates.
"""

from .context import BrowserContext, PerceptionContext, get_screen_context, probe_browser
from .errors import PerceptionError, PerceptionUnavailableError
from .screen import ScreenCapture, capture_screen
from .windows import WindowInfo, get_active_window, get_open_windows

__all__ = [
    "BrowserContext",
    "PerceptionContext",
    "PerceptionError",
    "PerceptionUnavailableError",
    "ScreenCapture",
    "WindowInfo",
    "capture_screen",
    "get_active_window",
    "get_open_windows",
    "get_screen_context",
    "probe_browser",
]
