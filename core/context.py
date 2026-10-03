"""Runtime environment snapshot and current-task context (Phase 7A).

Short-lived, explicitly-invalidated state — NOT a memory system and NOT a
second source of truth. Every fact here is re-derivable from the OS on demand
and is always presented to the model as an observation, never as proof that
an action succeeded (verification stays with the tools that can actually
verify).

- EnvironmentSnapshot: TTL-cached window/foreground facts built from
  `core.perception.get_screen_context()`; invalidated after every tool
  execution so the next read is a targeted refresh, not a stale claim.
- TaskContext: bounded recent actions + recent resources, so follow-up
  requests ("open it", "the file we just found") resolve against what OPERO
  actually just did.
- current_utterance(): freshness-first user utterance for tool guards. The
  live voice buffer wins over the session log, because on the Gemini-Live
  path the "User:" line is only appended at turn_complete — after the
  model's tool call.
"""

import re
import threading
import time
from collections import deque
from collections.abc import Sequence
from typing import Any

from .telemetry import record
from .visual.routing import last_user_utterance

ENV_TTL = 5.0          # seconds an environment snapshot stays fresh
MAX_WINDOWS = 12        # window titles carried into prompt/tool output
MAX_ACTIONS = 12        # recent actions kept in task context
MAX_RESOURCES = 8       # recent resources kept for reference resolution
MAX_RESULTS = 8         # last result set kept for ordinal references

# Ordinal language — "the second result", "open the third one". Resolution is
# deterministic against the LAST noted result set; never guessed.
_ORDINALS = {
    "first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3, "fifth": 4, "5th": 4, "sixth": 5, "6th": 5,
    "seventh": 6, "7th": 6, "eighth": 7, "8th": 7, "last": -1, "final": -1,
}
_ORDINAL_RE = re.compile(
    r"\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|6th|"
    r"seventh|7th|eighth|8th|last|final)\b", re.I)

# The model's reference words, resolved deterministically against TaskContext.
_KIND_WORDS = (
    ("browser tab", "tab"),
    ("tab", "tab"),
    ("window", "window"),
    ("folder", "folder"),
    ("directory", "folder"),
    ("file", "file"),
    ("application", "application"),
    ("app", "application"),
    ("browser", "browser"),
    ("page", "url"),
    ("site", "url"),
    ("url", "url"),
    ("program", "application"),
)
_PREV_MARKERS = ("previous", "earlier one", "other one", "the one before", "before that")

# Which argument identifies WHAT a tool acted on, for the recent-actions line.
_TARGET_KEYS = (
    "query", "url", "app_name", "path", "file_path", "name", "target",
    "topic", "title", "destination", "action", "text",
)

_FAIL_MARKERS = (
    "failed", "failure", "could not", "couldn't", "unable", "not found",
    "no such", "access denied", "refused", "invalid", "exception",
)


def summarize_args(args: dict[str, Any]) -> str:
    """Compact 'key=value' summary of the arguments that name a target."""
    if not isinstance(args, dict):
        return ""
    bits = [f"{k}={args.get(k)}" for k in _TARGET_KEYS if args.get(k) not in (None, "")]
    return "; ".join(bits)[:160]


def verdict(result_text: str) -> str:
    """Classify a tool result for the task-context line.

    'failed' = the tool reported failure; 'pending' = an on-screen
    confirmation is waiting; 'done' = the tool returned (which is NOT the
    same as independently verified success — the prompt says so explicitly).
    """
    text = result_text or ""
    lowered = text.lower()
    if "[CONFIRMATION_PENDING]" in text:
        return "pending"
    if "error" in lowered and "no error" not in lowered and "no errors" not in lowered:
        return "failed"
    if any(marker in lowered for marker in _FAIL_MARKERS):
        return "failed"
    return "done"


def current_utterance(live_text: str, session_log: Sequence[str]) -> str:
    """Freshest user utterance: the live (in-progress) voice buffer wins over
    the session log, which only receives 'User:' lines at turn_complete."""
    live = (live_text or "").strip()
    if live:
        return live
    return last_user_utterance(session_log)


class EnvironmentSnapshot:
    """TTL-cached OS window/foreground facts with explicit invalidation."""

    def __init__(self, ttl: float = ENV_TTL, clock=time.monotonic, probe=None):
        self._ttl = ttl
        self._clock = clock
        self._probe = probe
        self._lock = threading.Lock()
        self._data: dict | None = None
        self._ts = -1e18

    def get(self, force: bool = False) -> dict:
        """Snapshot dict; re-probes only when older than the TTL (or forced)."""
        now = self._clock()
        with self._lock:
            if not force and self._data is not None and (now - self._ts) < self._ttl:
                return self._data
            t0 = time.perf_counter()
            data = self._build()
            record("env_snapshot", (time.perf_counter() - t0) * 1000,
                   ok="error" not in data)
            self._data = data
            self._ts = now
            return data

    def _build(self) -> dict:
        # Test/injected path: the probe returns a PerceptionContext-shaped
        # object and gets the original 7A shape back, unchanged.
        if self._probe is not None:
            try:
                ctx = self._probe()
            except Exception as exc:  # perception must never break a tool call
                return {"error": f"environment unavailable: {exc}", "timestamp": None}
            active = ctx.active_window
            windows = [
                {"title": (w.title or "")[:90], "process": w.process}
                for w in list(ctx.windows)[:MAX_WINDOWS]
            ]
            browser = ctx.browser.to_dict() if ctx.browser and ctx.browser.detected else {"detected": False}
            return {
                "timestamp": ctx.timestamp,
                "foreground": (
                    {"title": (active.title or "")[:90], "process": active.process}
                    if active else None
                ),
                "window_count": len(ctx.windows),
                "open_windows": windows,
                "browser": browser,
            }

        # Real path: sectioned computer world model — geometry, state,
        # monitors and cursor with explicit per-section status, plus browser
        # detection from the observed foreground (no second window scan).
        try:
            from .perception.context import probe_browser
            from .world_model import world
            w = world()
            snap = w.snapshot()
            fg = w.foreground()
            browser = probe_browser(fg).to_dict() if fg else {"detected": False}
            return {
                "timestamp": time.time(),
                "foreground": (
                    {"title": (snap["foreground"]["title"] or "")[:90],
                     "process": snap["foreground"]["process"],
                     "state": snap["foreground"]["state"],
                     "rect": snap["foreground"]["rect"]}
                    if snap["foreground"] else None
                ),
                "window_count": snap["window_count"],
                "open_windows": snap["open_windows"],
                "browser": browser,
                "monitors": snap["monitors"],
                "cursor": snap["cursor"],
                "world_status": snap["status"],
            }
        except Exception as exc:  # perception must never break a tool call
            return {"error": f"environment unavailable: {exc}", "timestamp": None}

    def invalidate(self) -> None:
        """Drop the cached facts; the next get() performs a targeted refresh.
        Also drops world-model freshness — one dispatch may move windows,
        the cursor or the foreground app."""
        with self._lock:
            self._data = None
        try:
            from .world_model import world
            world().invalidate()
        except Exception:
            pass

    def prompt_block(self) -> str:
        """Compact [CURRENT ENVIRONMENT] block for the system prompt."""
        data = self.get()
        if "error" in data:
            return f"[CURRENT ENVIRONMENT]\n(unavailable: {data['error']})"
        fg = data.get("foreground")
        fg_line = (f"{fg['process']} — {fg['title']}" if fg else "(nothing focused)")
        titles = "; ".join(w["title"] or w["process"] for w in data.get("open_windows", []))
        lines = [
            "[CURRENT ENVIRONMENT]",
            f"Foreground: {fg_line}",
            f"Open windows ({data.get('window_count', 0)}): {titles or '(none)'}",
        ]
        browser = data.get("browser") or {}
        if browser.get("detected"):
            lines.append(f"Browser in foreground: {browser.get('name')}")
        if data.get("cursor"):
            lines.append(f"Cursor: ({data['cursor']['x']}, {data['cursor']['y']})")
        monitors = data.get("monitors") or []
        if monitors:
            prim = next((m for m in monitors if m.get("primary")), monitors[0])
            l, t, r, b = prim["rect"]
            lines.append(f"Monitors: {len(monitors)} (primary {r - l}x{b - t})")
        for sec, st in (data.get("world_status") or {}).items():
            if st in ("stale", "unknown", "unavailable"):
                lines.append(f"{sec}: {st} — re-check with environment_status refresh=true.")
        lines.append("Observed just now from the OS — re-check with environment_status before relying on it.")
        return "\n".join(lines)


class TaskContext:
    """Bounded short-term execution context: recent actions + resources."""

    def __init__(self, max_actions: int = MAX_ACTIONS, max_resources: int = MAX_RESOURCES,
                 clock=time.time):
        self._actions: deque[dict] = deque(maxlen=max_actions)
        self._resources: deque[dict] = deque(maxlen=max_resources)
        self._clock = clock
        self._current_folder: str | None = None
        self._results: list[tuple[str, str]] = []   # (kind, label) — last result set
        self._corrected = 0

    # ── recording ────────────────────────────────────────────────────────
    def note_action(self, tool: str, target: str = "", outcome: str = "done",
                    detail: str = "") -> dict:
        rec = {
            "tool": str(tool),
            "target": str(target)[:160],
            "outcome": str(outcome),
            "detail": str(detail)[:200],
            "ts": self._clock(),
        }
        self._actions.append(rec)
        return rec

    def note_resource(self, kind: str, identifier: str, label: str = "",
                      verified: bool = False) -> dict:
        """Record a resource OPERO just worked with; re-noting the same id
        refreshes it to 'most recent' instead of duplicating it."""
        identifier = str(identifier)
        keep = [r for r in self._resources if r["id"] != identifier]
        self._resources = deque(keep, maxlen=self._resources.maxlen)
        rec = {
            "kind": str(kind),
            "id": identifier,
            "label": str(label or identifier),
            "verified": bool(verified),
            "ts": self._clock(),
        }
        self._resources.append(rec)
        if kind == "folder":
            self._current_folder = identifier
        return rec

    def note_folder(self, path: Any) -> None:
        if path:
            self._current_folder = str(path)

    def note_results(self, kind: str, items) -> None:
        """Record the result LIST a tool just returned, so ordinals ('the
        second result', 'open the third one') resolve against real output.
        Replaces the previous set — results are the latest answer, not logs."""
        out: list[tuple[str, str]] = []
        for it in (items or [])[:MAX_RESULTS]:
            if it is None:
                continue
            if isinstance(it, dict):
                label = str(it.get("label") or it.get("title") or it.get("name")
                            or it.get("path") or it.get("id") or "")[:80]
            else:
                label = str(it)[:80]
            if label:
                out.append((str(kind), label))
        self._results = out

    def correct_resource(self, label: str, kind: str | None = None) -> dict:
        """User correction: the current resource reference was wrong —
        replace it. Records the correction so the fact is auditable, and
        never keeps the wrong entry as 'current'."""
        label = str(label).strip()
        cur = self.current_resource()
        keep = [r for r in self._resources if r is not cur]
        self._resources = deque(keep, maxlen=self._resources.maxlen)
        if not label:
            return cur or {}
        rec = self.note_resource(kind or (cur or {}).get("kind") or "file",
                                 label, label, verified=False)
        rec["corrected"] = True
        self._corrected += 1
        return rec

    @staticmethod
    def _ordinal(text: str) -> int | None:
        m = _ORDINAL_RE.search(text or "")
        if not m:
            return None
        return _ORDINALS[m.group(1).lower()]

    # ── reading ──────────────────────────────────────────────────────────
    @property
    def current_folder(self) -> str | None:
        return self._current_folder

    def current_resource(self, kind: str | None = None) -> dict | None:
        for res in reversed(self._resources):
            if kind is None or res["kind"] == kind:
                return res
        return None

    def previous_resource(self, kind: str | None = None) -> dict | None:
        """The resource before the current one (optionally same kind)."""
        skipped_current = False
        for res in reversed(self._resources):
            if kind is not None and res["kind"] != kind:
                continue
            if not skipped_current:
                skipped_current = True
                continue
            return res
        return None

    def resolve(self, phrase: str) -> dict | None:
        """Deterministic reference resolution for 'it' / 'that tab' / 'the
        previous one' / 'the second result'. Returns the matching resource or
        None — never guesses."""
        text = (phrase or "").strip().lower()
        if not text:
            return None
        kind = None
        for word, k in _KIND_WORDS:
            if word in text:
                kind = k
                break

        # Ordinals resolve against the LAST result set — and only that set.
        idx = self._ordinal(text)
        if idx is not None:
            hits = [(k, lab) for k, lab in self._results
                    if kind is None or k == kind]
            if not hits:
                return None
            pos = idx if idx >= 0 else len(hits) + idx
            if not (0 <= pos < len(hits)):
                return None
            k, lab = hits[pos]
            return {"kind": k, "id": lab, "label": f"result {pos + 1}: {lab}",
                    "verified": False, "ts": self._clock()}

        if any(marker in text for marker in _PREV_MARKERS):
            return self.previous_resource(kind)
        return self.current_resource(kind)

    def recent_actions(self, n: int = 5) -> list[dict]:
        return list(self._actions)[-max(1, int(n)):]

    def recent_resources(self, n: int = 5) -> list[dict]:
        return list(self._resources)[-max(1, int(n)):]

    def summary(self) -> dict:
        """JSON-safe summary for the environment_status tool."""
        return {
            "current_folder": self._current_folder,
            "current_resource": self.current_resource(),
            "recent_actions": self.recent_actions(),
            "recent_resources": self.recent_resources(),
            "last_results": [lab for _, lab in self._results],
            "corrections": self._corrected,
        }

    def prompt_block(self) -> str:
        """Compact [CURRENT TASK CONTEXT] block; '' when nothing is known."""
        if not self._actions and not self._resources and not self._current_folder:
            return ""
        lines = ["[CURRENT TASK CONTEXT]"]
        if self._current_folder:
            lines.append(f"Current folder: {self._current_folder}")
        cur = self.current_resource()
        if cur:
            age = max(0, int(self._clock() - cur["ts"]))
            state = "verified" if cur["verified"] else "unverified"
            lines.append(f"Current resource: {cur['kind']} {cur['label']} ({state}, {age}s ago)")
        if self._results:
            lines.append("Last results (pick with 'the second one' etc.): "
                         + "; ".join(f"{i + 1}. {lab}" for i, (_, lab) in enumerate(self._results)))
        if self._actions:
            lines.append("Recent actions (outcomes are tool-reported: done = returned, "
                         "failed = tool-reported failure, pending = waiting for on-screen confirmation):")
            for rec in self.recent_actions(5):
                target = f" {rec['target']}" if rec["target"] else ""
                lines.append(f"  - {rec['tool']}{target} → {rec['outcome']}")
        lines.append('Words like "it", "this", "that", "there", "the file we just '
                     'found" or "the one I opened" refer to the current resource; '
                     '"previous/other one" to the one before it; ordinals ("the '
                     'second result") to the last result list above. If a reference '
                     'is wrong, correct it with context_note (correct=...) — do not '
                     'keep arguing with the wrong target. If nothing fits, ask.')
        return "\n".join(lines)


# ── process-wide singletons (double-checked locking, like get_visual_router) ──
_ENV: EnvironmentSnapshot | None = None
_TASK: TaskContext | None = None
_lock = threading.Lock()


def env_cache() -> EnvironmentSnapshot:
    global _ENV
    if _ENV is None:
        with _lock:
            if _ENV is None:
                _ENV = EnvironmentSnapshot()
    return _ENV


def task_ctx() -> TaskContext:
    global _TASK
    if _TASK is None:
        with _lock:
            if _TASK is None:
                _TASK = TaskContext()
    return _TASK
