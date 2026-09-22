"""Tiny synchronous event bus for the visual system.

The director emits domain events (state changed, intent began/ended, errors);
the UI layer and tests subscribe without the director knowing about them.
Deliberately minimal — no async, no priority, no persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class VisualEvent:
    """A single visual-system event."""

    kind: str            # e.g. "state", "intent_begin", "visual_error"
    payload: Any = None  # event-specific data


class VisualBus:
    """Publish/subscribe with per-kind handlers (callable(event))."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[VisualEvent], None]]] = {}

    def subscribe(self, kind: str, fn: Callable[[VisualEvent], None]) -> None:
        self._subs.setdefault(kind, []).append(fn)

    def publish(self, kind: str, payload: Any = None) -> None:
        ev = VisualEvent(kind=kind, payload=payload)
        for fn in list(self._subs.get(kind, ())):
            try:
                fn(ev)
            except Exception:
                # A subscriber must never take the visual system (or OPERO)
                # down with it.
                continue

    def unsubscribe(self, kind: str, fn: Callable) -> None:
        self._subs.setdefault(kind, []).remove(fn) if fn in self._subs.get(kind, []) else None