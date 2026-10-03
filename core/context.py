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
        try:
            if self._probe is not None:
                ctx = self._probe()
            else:
                from .perception import get_screen_context
                ctx = get_screen_context(capture=False)
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

    def invalidate(self) -> None:
        """Drop the cached facts; the next get() performs a targeted refresh."""
        with self._lock:
            self._data = None

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
        previous one'. Returns the matching resource or None — never guesses."""
        text = (phrase or "").strip().lower()
        if not text:
            return None
        kind = None
        for word, k in _KIND_WORDS:
            if word in text:
                kind = k
                break
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
        if self._actions:
            lines.append("Recent actions (outcomes are tool-reported: done = returned, "
                         "failed = tool-reported failure, pending = waiting for on-screen confirmation):")
            for rec in self.recent_actions(5):
                target = f" {rec['target']}" if rec["target"] else ""
                lines.append(f"  - {rec['tool']}{target} → {rec['outcome']}")
        lines.append('Words like "it", "this", "that", "there", "the file we just '
                     'found" or "the one I opened" refer to the current resource; '
                     '"previous/other one" to the one before it. If nothing fits, ask.')
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
