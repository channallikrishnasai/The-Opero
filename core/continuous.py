"""Continuous cursor motion with interruption (Phase 7B).

A small engine for repeated/patterned mouse movement (line, circle, figure
eight, square, spiral) that can be started, modified while running (faster /
slower / bigger / smaller / more repeats), and STOPPED — including from the
UI interrupt path, so "stop drawing" actually stops the machine.

Bounded by design: duration and size are capped, the loop checks the stop
event every leg, and stop() releases any held mouse button. Geometry is a
pure function (`pattern_points`) so the math is testable without a display;
only `_default_move` touches pyautogui.
"""

import math
import threading
import time

MAX_DURATION = 60.0        # seconds per pass — hard cap
MAX_SIZE = 2000.0          # px — hard cap
MAX_REPEAT = 100
STEPS = 48                 # points per pass

PATTERNS = ("line", "circle", "figure_eight", "square", "spiral")


def pattern_points(pattern: str, cx: int, cy: int, size: float,
                   steps: int = STEPS) -> list[tuple[int, int]]:
    """Deterministic point list for one pass of a pattern.

    `size` is the overall extent in px (length/diameter), centered on
    (cx, cy). Returns [] for unknown patterns — never a made-up path.
    """
    pattern = str(pattern or "").lower().strip()
    size = max(4.0, min(float(size or 100.0), MAX_SIZE))
    r = size / 2.0
    out: list[tuple[int, int]] = []
    if pattern == "line":
        for i in range(steps + 1):
            out.append((int(cx - r + size * i / steps), int(cy)))
    elif pattern == "circle":
        for i in range(steps + 1):
            t = 2.0 * math.pi * i / steps
            out.append((int(cx + r * math.cos(t)), int(cy + r * math.sin(t))))
    elif pattern == "square":
        per = 4 * size
        for i in range(steps + 1):
            d = per * i / steps
            side, off = divmod(d, size)
            if side == 0:
                out.append((int(cx - r + off), int(cy - r)))
            elif side == 1:
                out.append((int(cx + r), int(cy - r + off)))
            elif side == 2:
                out.append((int(cx + r - off), int(cy + r)))
            else:
                out.append((int(cx - r), int(cy + r - off)))
    elif pattern == "figure_eight":
        a = r
        for i in range(steps + 1):
            t = 2.0 * math.pi * i / steps
            out.append((int(cx + a * math.sin(t)), int(cy + a * math.sin(t) * math.cos(t))))
    elif pattern == "spiral":
        turns = 3.0
        for i in range(steps * 2 + 1):
            t = turns * 2.0 * math.pi * i / (steps * 2)
            rr = r * i / (steps * 2)
            out.append((int(cx + rr * math.cos(t)), int(cy + rr * math.sin(t))))
    return out


def _default_move(x: int, y: int) -> None:
    import pyautogui
    pyautogui.moveTo(int(x), int(y), duration=0)


def _default_position() -> tuple[int, int]:
    try:
        import pyautogui
        p = pyautogui.position()
        return int(p.x), int(p.y)
    except Exception:
        return 0, 0


class ActionEngine:
    """At most one running pattern; modify() retunes it live."""

    def __init__(self, move=None, position=None, sleep=time.sleep):
        self._move = move or _default_move
        self._position = position or _default_position
        self._sleep = sleep
        self._lock = threading.Lock()
        self._run = None            # dict describing the live run
        self._thread: threading.Thread | None = None
        self._last: dict = {"state": "idle"}

    # ── control surface ──────────────────────────────────────────────────
    def start(self, spec: dict) -> dict:
        spec = spec or {}
        pattern = str(spec.get("pattern", "")).lower().strip()
        if pattern not in PATTERNS:
            return {"state": "failed",
                    "error": f"unknown pattern '{spec.get('pattern')}' — "
                             f"use one of: {', '.join(PATTERNS)}"}
        try:
            cx = int(spec.get("x", self._position()[0]))
            cy = int(spec.get("y", self._position()[1]))
            size = max(4.0, min(float(spec.get("size", 200.0)), MAX_SIZE))
            duration = max(0.2, min(float(spec.get("duration", 2.0)), MAX_DURATION))
            repeat = max(1, min(int(spec.get("repeat", 1)), MAX_REPEAT))
        except (TypeError, ValueError) as exc:
            return {"state": "failed", "error": f"bad parameter: {exc}"}

        with self._lock:
            if self._run and self._run.get("state") == "running":
                return {"state": "already_running",
                        "current": self._status_locked(),
                        "error": "a pattern is already running — stop it first "
                                 "or ask to modify it."}
            self._run = {
                "state": "running", "pattern": pattern, "cx": cx, "cy": cy,
                "size": size, "duration": duration, "repeat": repeat,
                "speed": 1.0, "scale": 1.0,
                "pass_no": 0, "points": 0, "button": str(spec.get("button", "") or ""),
                "started": time.monotonic(), "error": None,
                "final": None, "stop": threading.Event(), "reason": "",
            }
            run = self._run
        self._thread = threading.Thread(target=self._loop, args=(run,),
                                        daemon=True, name="opero-continuous")
        self._thread.start()
        return {"state": "running", **self._public(run)}

    def status(self) -> dict:
        with self._lock:
            if self._run:
                return self._status_locked()
            return dict(self._last)

    def modify(self, changes: dict) -> dict:
        changes = changes or {}
        with self._lock:
            run = self._run
            if not run or run.get("state") != "running":
                return {"state": "idle", "error": "nothing is running."}
            if "speed" in changes:
                try:
                    run["speed"] = max(0.1, min(float(changes["speed"]), 10.0))
                except (TypeError, ValueError):
                    pass
            if "scale" in changes:
                try:
                    run["scale"] = max(0.1, min(float(changes["scale"]), 10.0))
                except (TypeError, ValueError):
                    pass
            if "size" in changes:
                try:
                    run["size"] = max(4.0, min(float(changes["size"]), MAX_SIZE))
                except (TypeError, ValueError):
                    pass
            if "duration" in changes:
                try:
                    run["duration"] = max(0.2, min(float(changes["duration"]), MAX_DURATION))
                except (TypeError, ValueError):
                    pass
            if "repeat" in changes:
                try:
                    run["repeat"] = max(1, min(int(changes["repeat"]), MAX_REPEAT))
                except (TypeError, ValueError):
                    pass
            return {"state": "modified", **self._public(run)}

    def stop(self, reason: str = "stopped") -> dict:
        with self._lock:
            run = self._run
            if run is None:
                return dict(self._last)
            run["stop"].set()
            run["reason"] = reason
            thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        with self._lock:
            run["state"] = "stopped" if run.get("state") == "running" else run["state"]
            self._last = {"state": "stopped", "reason": reason,
                          **{k: run[k] for k in ("pattern", "pass_no", "points", "final")}}
            out = dict(self._last)
            self._run = None
        return out

    # ── internals ────────────────────────────────────────────────────────
    def _status_locked(self) -> dict:
        return {"state": self._run.get("state"), **self._public(self._run)}

    @staticmethod
    def _public(run: dict) -> dict:
        return {k: run[k] for k in ("pattern", "cx", "cy", "size", "duration",
                                    "repeat", "speed", "scale", "pass_no",
                                    "points", "error", "final")}

    def _loop(self, run: dict) -> None:
        held = False
        try:
            if run["button"]:
                import pyautogui
                pyautogui.mouseDown(button=run["button"])
                held = True
            while not run["stop"].is_set() and run["pass_no"] < run["repeat"]:
                with self._lock:
                    size = run["size"] * run["scale"]
                    dur = run["duration"] / run["speed"]
                    cx, cy, pattern = run["cx"], run["cy"], run["pattern"]
                pts = pattern_points(pattern, cx, cy, size)
                if not pts:
                    with self._lock:
                        run["state"] = "failed"
                        run["error"] = f"no geometry for '{pattern}'"
                    return
                leg = max(0.0, dur / len(pts))
                for x, y in pts:
                    if run["stop"].is_set():
                        break
                    self._move(x, y)
                    if leg > 0:
                        self._sleep(leg)
                    with self._lock:
                        run["points"] += 1
                with self._lock:
                    run["pass_no"] += 1
            with self._lock:
                if run["state"] == "running":
                    run["state"] = "completed"
                run["final"] = self._position()
        except Exception as exc:  # FAILSAFE corner, display loss, …
            with self._lock:
                run["state"] = "failed"
                run["error"] = str(exc)
        finally:
            if held:
                try:
                    import pyautogui
                    pyautogui.mouseUp(button=run["button"])
                except Exception:
                    pass
            with self._lock:
                run.setdefault("final", self._position())


# ── process-wide singleton ───────────────────────────────────────────────────
_engine: ActionEngine | None = None
_lock = threading.Lock()


def engine() -> ActionEngine:
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = ActionEngine()
    return _engine
