"""VisualDirector — the single entry point of the visual layer.

Pipeline (matches the brief, with Gemini on the far side):

    Gemini (tool call) -> validated VisualIntent -> VisualDirector
                        -> renderer directive (pure data) -> THREE.js scene

The director is deliberately thin and framework-free:
  * it validates (never trusts) incoming intent,
  * it emits domain events on a VisualBus (state, intent_begin, intent_end,
    visual_error) so the UI/tests observe it without coupling,
  * it talks to the renderer through a tiny bridge object, and
  * it NEVER blocks the voice loop — a failed visualisation is a log line, an
    event and a graceful message, not an exception.

Thread-safety: apply_intent/return_to_idle may be called from Gemini's executor
thread.  Everything stateful is behind a lock; the bridge hop is fire-and-forget.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from core.visual.events import VisualBus
from core.visual.intent import (
    VisualError,
    VisualIntent,
    intent_to_directive,
    validate_intent,
)

log = logging.getLogger("opero.visual")


class RendererBridge:
    """Minimal contract between the director and a renderer backend.

    `send` is the only required method; a bridge that is absent (None) makes the
    whole layer a graceful no-op (headless/CI/no-WebGL machines) while the
    QPainter avatar keeps running untouched.
    """

    def send(self, directive: dict) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class _UiBridge(RendererBridge):
    """Bridges to the Qt window's WebGL layer via the OperaUI proxy."""

    def __init__(self, player: Any):
        self._player = player

    def send(self, directive: dict) -> None:
        win = getattr(self._player, "_win", None)
        apply = getattr(win, "apply_visual", None) if win is not None else None
        if apply is not None:
            try:
                apply(directive)
            except Exception:
                log.exception("apply_visual failed")


class VisualDirector:
    """Validates visual intent and drives the renderer bridge."""

    def __init__(self, bridge=None, bus=None):
        self._bridge = bridge
        self._bus = bus or VisualBus()
        self._lock = threading.Lock()
        self._active = None
        self._generation = 0
        self._return_timer = None
        self._state = "IDLE"

    # ── configuration ────────────────────────────────────────────────────────
    @property
    def bus(self) -> VisualBus:
        return self._bus

    @property
    def available(self) -> bool:
        return self._bridge is not None

    def set_bridge(self, bridge) -> None:
        self._bridge = bridge

    # ── intent pipeline ──────────────────────────────────────────────────────
    def apply_intent(self, raw) -> str:
        """Validate and apply a visual intent.  Never raises.

        Returns a short human-readable status string the assistant can speak.
        """
        # Validation errors are routine (a model hallucinating an object id is
        # not a crash) — log and continue the voice response.
        try:
            intent = validate_intent(raw)
        except VisualError as exc:
            log.warning("visual intent rejected: %s", exc)
            self._bus.publish("visual_error", {"reason": str(exc), "raw": raw})
            return f"Visualisation not available: {exc}"

        directive = intent_to_directive(intent)

        with self._lock:
            self._generation += 1
            gen = self._generation
            self._active = directive
            if self._return_timer is not None:
                self._return_timer.cancel()
                self._return_timer = None

        self._bus.publish("intent_begin", directive)
        self._set_scene_state("STORY" if intent.mode == "story" else "VISUALIZING")

        if self._bridge is not None:
            try:
                self._bridge.send(directive)
            except Exception:
                log.exception("renderer failed to apply intent")
                self._bus.publish("visual_error",
                                  {"reason": "renderer error", "raw": raw})

        if intent.auto_return:
            timer = threading.Timer(max(intent.duration + 1.5, 2.5),
                                    self.return_to_idle, args=(gen,))
            timer.daemon = True
            with self._lock:
                self._return_timer = timer
            timer.start()

        desc = f"Visualising {directive['subject'] or 'the scene'}"
        desc += f" ({directive['material']}, {directive['camera']} camera)"
        return desc

    def return_to_idle(self, generation=None) -> None:
        """Dissolve the scene and hand the stage back to the avatar."""
        with self._lock:
            if generation is not None and generation != self._generation:
                return                      # a newer intent owns the stage
            self._active = None
            if self._return_timer is not None:
                self._return_timer.cancel()
                self._return_timer = None

        self._bus.publish("intent_end", {"return_to": "avatar"})
        self._set_scene_state("RETURN")
        if self._bridge is not None:
            try:
                self._bridge.send({"op": "return", "return_to": "avatar"})
            except Exception:
                log.exception("renderer failed to return")

    # ── state mirroring ──────────────────────────────────────────────────────
    def _set_scene_state(self, name: str) -> None:
        with self._lock:
            self._state = name
        self._bus.publish("state", {"state": name})

    def on_state(self, name: str) -> None:
        """Record + broadcast; the window already forwards states to the
        renderer, so the director only mirrors them here."""
        name = str(name or "IDLE").upper()
        with self._lock:
            self._state = name
        self._bus.publish("state", {"state": name})

    def diagnostics(self) -> dict:
        with self._lock:
            return {
                "available": self.available,
                "state": self._state,
                "active": bool(self._active),
                "subject": (self._active or {}).get("subject"),
            }


# ── module-level singleton (set once from main.py) ───────────────────────────
_director = None


def get_visual_director():
    """Return the active director, or None (visualisation simply unavailable)."""
    return _director


def set_visual_director(director=None) -> None:
    global _director
    _director = director


def setup_visual_system(player: Any) -> VisualDirector:
    """Wire the visual system to a running UI (called once from main.py).

    Never raises: any failure leaves OPERO running exactly as before.  On
    machines without WebGL the bridge is a no-op and the QPainter avatar keeps
    running untouched.
    """
    win = getattr(player, "_win", None)
    real_bridge = _UiBridge(player) if win is not None else None
    director = VisualDirector(bridge=real_bridge)
    set_visual_director(director)
    # Push the measured head geometry into the renderer (single source of truth).
    push = getattr(win, "push_face_mesh", None) if win is not None else None
    if push is not None:
        try:
            push()
        except Exception:
            log.exception("face mesh push failed")
    return director