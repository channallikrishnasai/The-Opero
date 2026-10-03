"""Computer World Model (Phase 7B).

The smallest read-model over what the OS actually reports: monitors, windows
(with geometry/state/z-order), the cursor, and optionally browser tabs when a
probe is supplied. It is an OBSERVATION layer — sections carry an explicit
status (known / stale / unknown / unavailable) and unknown is never presented
as fact. Control/verification stays with the tools that perform the action.

Deliberately not a manager: no action dispatch, no memory, no planning.
`EnvironmentSnapshot` (core/context.py) consumes `ComputerWorld.snapshot()`
for its prompt block; tools query the accessors directly for targeting.
"""

import threading
import time
from collections.abc import Callable
from typing import Any

KNOWN = "known"
STALE = "stale"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

WORLD_TTL = 5.0        # seconds a section's data stays fresh
MAX_TAB_LIST = 24       # browser tabs carried into prompt/tool output


class _Section:
    __slots__ = ("status", "ts", "data", "error")

    def __init__(self):
        self.status = UNKNOWN
        self.ts = -1e18
        self.data: Any = None
        self.error: str | None = None


class ComputerWorld:
    """TTL-cached, per-section observation cache with targeted refresh."""

    def __init__(self, ttl: float = WORLD_TTL, clock=time.monotonic,
                 probes: dict[str, Callable[[], Any]] | None = None):
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._sections: dict[str, _Section] = {}
        self._probes: dict[str, Callable[[], Any]] = dict(probes or {})

    # ── internals ────────────────────────────────────────────────────────
    def _default_probe(self, name: str) -> Callable[[], Any]:
        def _windows():
            from .perception import get_open_windows, get_active_window
            return {"windows": get_open_windows(), "foreground": get_active_window()}

        def _monitors():
            from .perception.windows import get_monitors
            return get_monitors()

        def _cursor():
            from .perception.windows import get_cursor_pos
            return get_cursor_pos()

        return {"windows": _windows, "monitors": _monitors, "cursor": _cursor}[name]

    def _run_probe(self, name: str) -> None:
        probe = self._probes.get(name) or self._default_probe(name)
        sec = self._sections.setdefault(name, _Section())
        try:
            data = probe()
        except Exception as exc:
            # Distinguish "platform cannot provide this" from "probe failed".
            status = UNAVAILABLE if type(exc).__name__ == "PerceptionUnavailableError" else UNKNOWN
            sec.status = status
            sec.error = str(exc)
            sec.ts = self._clock()
            return
        sec.status = KNOWN
        sec.error = None
        sec.data = data
        sec.ts = self._clock()

    def _fresh(self, sec: _Section, force: bool) -> bool:
        if sec.data is None and sec.status == UNKNOWN:
            return False
        if force:
            return False
        return (self._clock() - sec.ts) < self._ttl

    # ── refresh / status ─────────────────────────────────────────────────
    def refresh(self, section: str | None = None, force: bool = False) -> dict[str, str]:
        """Targeted refresh: one section (or all). Returns section -> status."""
        names = [section] if section else ["windows", "monitors", "cursor"]
        out: dict[str, str] = {}
        for name in names:
            with self._lock:
                sec = self._sections.setdefault(name, _Section())
                if not self._fresh(sec, force):
                    self._run_probe(name)
                out[name] = self.status(name)
        return out

    def status(self, section: str) -> str:
        sec = self._sections.get(section)
        if sec is None or (sec.status == UNKNOWN and sec.data is None):
            return UNKNOWN
        if sec.status in (UNAVAILABLE, UNKNOWN):
            return sec.status
        if (self._clock() - sec.ts) >= self._ttl:
            return STALE
        return KNOWN

    def invalidate(self) -> None:
        """Drop freshness: the next read performs a targeted refresh."""
        with self._lock:
            for sec in self._sections.values():
                sec.ts = -1e18

    def _read(self, name: str) -> Any:
        with self._lock:
            sec = self._sections.setdefault(name, _Section())
            if not self._fresh(sec, False):
                self._run_probe(name)
            return sec.data

    # ── accessors ────────────────────────────────────────────────────────
    def windows(self) -> list[Any]:
        data = self._read("windows") or {}
        return list(data.get("windows") or [])

    def foreground(self) -> Any:
        data = self._read("windows") or {}
        return data.get("foreground")

    def monitors(self) -> list[Any]:
        return list(self._read("monitors") or [])

    def cursor(self) -> tuple[int, int] | None:
        return self._read("cursor")

    def find_windows(self, query: str) -> list[Any]:
        """Windows whose title/process contains every token of the query."""
        tokens = [t for t in str(query or "").lower().split() if t]
        if not tokens:
            return []
        out = []
        for w in self.windows():
            hay = f"{getattr(w, 'title', '')} {getattr(w, 'process', '')}".lower()
            if all(t in hay for t in tokens):
                out.append(w)
        return out

    def primary_rect(self) -> tuple[int, int, int, int] | None:
        mons = self.monitors()
        for m in mons:
            if getattr(m, "primary", False):
                return tuple(m.rect)
        return tuple(mons[0].rect) if mons else None

    def set_probe(self, name: str, probe: Callable[[], Any] | None) -> None:
        """Attach/replace a section probe (browser tabs, tests)."""
        with self._lock:
            if probe is None:
                self._probes.pop(name, None)
            else:
                self._probes[name] = probe
            self._sections.pop(name, None)

    # ── composite views ──────────────────────────────────────────────────
    def snapshot(self) -> dict[str, Any]:
        """JSON-safe world snapshot with per-section statuses."""
        data = self._read("windows") or {}
        windows = list(data.get("windows") or [])
        fg = data.get("foreground")
        monitors = self.monitors()      # read BEFORE status so it is not "unknown"
        cursor = self.cursor()
        return {
            "status": {
                "windows": self.status("windows"),
                "monitors": self.status("monitors"),
                "cursor": self.status("cursor"),
            },
            "foreground": (
                {"title": getattr(fg, "title", ""), "process": getattr(fg, "process", ""),
                 "state": getattr(fg, "state", "unknown"), "rect": getattr(fg, "rect", None)}
                if fg else None
            ),
            "window_count": len(windows),
            "open_windows": [
                {"title": (getattr(w, "title", "") or "")[:90],
                 "process": getattr(w, "process", ""),
                 "state": getattr(w, "state", "unknown"),
                 "rect": getattr(w, "rect", None),
                 "foreground": fg is not None and getattr(w, "hwnd", 0) == getattr(fg, "hwnd", -1)}
                for w in windows[:12]
            ],
            "monitors": [
                {"index": getattr(m, "index", i), "rect": tuple(getattr(m, "rect", ())),
                 "primary": getattr(m, "primary", False)}
                for i, m in enumerate(monitors[:8])
            ],
            "cursor": (lambda p: {"x": p[0], "y": p[1]} if p else None)(cursor),
        }

    def prompt_block(self) -> str:
        """Compact [COMPUTER WORLD] facts for the system prompt."""
        snap = self.snapshot()
        st = snap["status"]
        lines = ["[COMPUTER WORLD]"]
        fg = snap["foreground"]
        if st["windows"] == UNAVAILABLE:
            lines.append("Windows: unavailable on this platform.")
        else:
            if fg:
                lines.append(f"Foreground: {fg['process']} — {fg['title']} ({fg['state']})")
            else:
                lines.append("Foreground: (nothing focused)")
            lines.append(f"Windows ({snap['window_count']}): "
                         + "; ".join(f"{w['title'] or w['process']}[{w['state']}]"
                                     for w in snap["open_windows"]) or "(none)")
        if st["monitors"] == KNOWN:
            prim = next((m for m in snap["monitors"] if m["primary"]), None)
            if prim:
                l, t, r, b = prim["rect"]
                lines.append(f"Primary monitor: {r - l}x{b - t} at ({l},{t}); {len(snap['monitors'])} monitor(s)")
        if st["cursor"] == KNOWN and snap["cursor"]:
            lines.append(f"Cursor: ({snap['cursor']['x']}, {snap['cursor']['y']})")
        for name in ("windows", "monitors", "cursor"):
            if st[name] in (STALE, UNKNOWN):
                lines.append(f"{name}: {st[name]} — re-check with environment_status refresh=true.")
        return "\n".join(lines)


# ── spatial language (pure, deterministic) ──────────────────────────────────

_ANCHORS = {
    "top-left": (0.0, 0.0), "topleft": (0.0, 0.0), "left top": (0.0, 0.0),
    "top-right": (1.0, 0.0), "topright": (1.0, 0.0), "right top": (1.0, 0.0),
    "bottom-left": (0.0, 1.0), "bottomleft": (0.0, 1.0), "left bottom": (0.0, 1.0),
    "bottom-right": (1.0, 1.0), "bottomright": (1.0, 1.0), "right bottom": (1.0, 1.0),
    "top": (0.5, 0.0), "upper": (0.5, 0.0),
    "bottom": (0.5, 1.0), "lower": (0.5, 1.0),
    "left": (0.0, 0.5), "right": (1.0, 0.5),
    "center": (0.5, 0.5), "middle": (0.5, 0.5), "centre": (0.5, 0.5),
}


def anchor_point(rect: tuple[int, int, int, int], phrase: str) -> tuple[int, int] | None:
    """Map spatial language onto a pixel rect (left, top, right, bottom).

    'top-left', 'bottom right', 'center', 'left', 'lower edge' … -> point.
    Returns None when the phrase names no anchor — never guesses.
    """
    if not rect:
        return None
    text = str(phrase or "").lower().replace("-", " ").replace("_", " ").strip()
    if not text:
        return None
    left, top, right, bottom = rect
    fx = fy = None
    for word, (ax, ay) in _ANCHORS.items():
        norm = word.replace("-", " ")
        if norm in text or word in text:
            fx, fy = ax, ay
            break
    if fx is None:
        return None
    x = int(left + fx * max(0, right - left))
    y = int(top + fy * max(0, bottom - top))
    # Nudge inward from exact edges so the point lands inside the region.
    if fx == 0.0:
        x += 8
    elif fx == 1.0:
        x -= 8
    if fy == 0.0:
        y += 8
    elif fy == 1.0:
        y -= 8
    return (max(left, min(right - 1, x)), max(top, min(bottom - 1, y)))


def parse_spatial(phrase: str) -> bool:
    """Does this phrase name a spatial anchor at all?"""
    text = str(phrase or "").lower().replace("-", " ")
    return any(w.replace("-", " ") in text for w in _ANCHORS)


def pick_window(windows: list[Any], phrase: str) -> Any | None:
    """Resolve spatial/ordinal language against the z-ordered window list.

    windows[0] is topmost. Supports: foreground/front/top, background/behind
    (bottom-most), second/third/Nth, right-most, left-most, plus a title
    query ('chrome on the right' matches chrome windows first).
    Returns None when nothing fits — never guesses.
    """
    if not windows:
        return None
    text = str(phrase or "").lower().replace("-", " ").strip()
    if not text:
        return None

    # Narrow by title/process tokens when the phrase names something.
    tokens = [w for w in text.split() if w not in
              {"the", "a", "on", "in", "to", "of", "window", "right", "left",
               "top", "bottom", "background", "foreground", "front", "behind",
               "second", "third", "first", "last", "other", "one"}]
    pool = list(windows)
    if tokens:
        matched = [w for w in pool
                   if all(t in f"{getattr(w, 'title', '')} {getattr(w, 'process', '')}".lower()
                          for t in tokens)]
        if matched:
            pool = matched

    if any(m in text for m in ("background", "behind", "back")):
        return pool[-1]
    if any(m in text for m in ("foreground", "front", "focused")):
        return pool[0]
    if "right" in text:
        return max(pool, key=lambda w: _center(w)[0])
    if "left" in text and "right" not in text:
        return min(pool, key=lambda w: _center(w)[0])

    for word, idx in (("first", 0), ("1st", 0), ("second", 1), ("2nd", 1),
                      ("third", 2), ("3rd", 2), ("fourth", 3), ("4th", 3),
                      ("fifth", 4), ("5th", 4), ("last", -1), ("final", -1)):
        if word in text:
            pos = idx if idx >= 0 else len(pool) + idx
            return pool[pos] if 0 <= pos < len(pool) else None
    return pool[0]


def _center(w: Any) -> tuple[int, int]:
    rect = getattr(w, "rect", None)
    if not rect:
        return (0, 0)
    return ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)


# ── process-wide singleton (double-checked locking, like get_visual_router) ──
_world: ComputerWorld | None = None
_lock = threading.Lock()


def world() -> ComputerWorld:
    global _world
    if _world is None:
        with _lock:
            if _world is None:
                _world = ComputerWorld()
    return _world
