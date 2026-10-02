"""Unified perception context: screen, windows, and browser — observation only.

Built only on explicit call; nothing polls continuously, and the context never
carries image bytes (screen section is metadata at most), so it is safe to hand
to future Gemini reasoning as structured text.
"""

import importlib.util
import shutil
import time
from dataclasses import dataclass, field
from typing import Any

from .errors import PerceptionError
from .screen import capture_screen
from .windows import WindowInfo, get_active_window, get_open_windows

BROWSER_PROCESS_NAMES = frozenset(
    {"brave", "chrome", "chromium", "edge", "firefox", "iexplore", "msedge", "opera", "vivaldi"}
)


def _browser_name(process: str | None) -> str | None:
    if not process:
        return None
    name = process.lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name if name in BROWSER_PROCESS_NAMES else None


def _integration_available() -> bool:
    """True when a browser-driving integration (playwright or the MCP runner) is present."""
    try:
        if importlib.util.find_spec("playwright") is not None:
            return True
    except (ImportError, ValueError):
        pass
    return shutil.which("npx") is not None


@dataclass(frozen=True)
class BrowserContext:
    detected: bool
    name: str | None = None
    pid: int | None = None
    title: str | None = None
    integration_available: bool = False
    capabilities: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "name": self.name,
            "pid": self.pid,
            "title": self.title,
            "integration_available": self.integration_available,
            "capabilities": dict(self.capabilities),
        }


def probe_browser(active: WindowInfo | None = None) -> BrowserContext:
    """Detect whether the foreground window is a browser and what OPERO could do with it.

    Detection is window-level observation. Capabilities reflect whether the
    browser-driving integration is installed — page/tab control itself stays in
    the action engine (actions/browser_control.py), never invoked from here.
    """
    if active is None:
        try:
            active = get_active_window()
        except PerceptionError:
            active = None
    name = _browser_name(active.process) if active else None
    integration = _integration_available()
    capabilities = {
        "enumerate_tabs": integration,
        "inspect_page": integration,
        "navigate": integration,
        "click": integration,
        "type": integration,
    }
    return BrowserContext(
        detected=name is not None,
        name=name,
        pid=active.pid if name else None,
        title=active.title if name else None,
        integration_available=integration,
        capabilities=capabilities,
    )


@dataclass(frozen=True)
class PerceptionContext:
    timestamp: float
    browser: BrowserContext
    active_window: WindowInfo | None = None
    windows: tuple[WindowInfo, ...] = ()
    screen: dict[str, Any] | None = None  # capture metadata only; never image bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "screen": dict(self.screen) if self.screen else None,
            "windows": {
                "active_window": self.active_window.to_dict() if self.active_window else None,
                "windows": [window.to_dict() for window in self.windows],
            },
            "browser": self.browser.to_dict(),
        }


def get_screen_context(*, capture: bool = False) -> PerceptionContext:
    """One explicit perception snapshot; degrades to partial context when a layer is unavailable."""
    try:
        active = get_active_window()
        open_windows = get_open_windows()
    except PerceptionError:
        active, open_windows = None, []
    browser = probe_browser(active)
    screen_meta = capture_screen().to_dict() if capture else None
    return PerceptionContext(
        timestamp=time.time(),
        browser=browser,
        active_window=active,
        windows=tuple(open_windows),
        screen=screen_meta,
    )
