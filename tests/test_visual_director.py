"""VisualDirector contract: intent in -> directive out through a bridge,
fallback when no bridge, events for the UI, and never an exception.

No GPU, no WebGL, no Qt — these run anywhere pytest runs.
"""

from __future__ import annotations

import threading

from core.visual.director import (
    RendererBridge,
    VisualDirector,
    get_visual_director,
    set_visual_director,
)
from core.visual.events import VisualBus


class FakeBridge(RendererBridge):
    def __init__(self):
        self.directives = []

    def send(self, directive):
        self.directives.append(dict(directive))


def test_director_basic_flow():
    bridge = FakeBridge()
    bus = VisualBus()
    kinds = []
    bus.subscribe("intent_begin", lambda e: kinds.append(("begin", e.payload["subject"])))
    bus.subscribe("intent_end", lambda e: kinds.append(("end", None)))
    d = VisualDirector(bridge=bridge, bus=bus)

    result = d.apply_intent({"subject": "apple", "duration": 4,
                             "auto_return": False, "camera": "focus"})
    assert "apple" in result
    assert len(bridge.directives) == 1
    assert bridge.directives[0]["subject"] == "apple"
    assert bridge.directives[0]["op"] == "show"
    assert ("begin", "apple") in kinds
    assert d.diagnostics()["active"] is True
    assert d.diagnostics()["subject"] == "apple"

    d.return_to_idle(d._generation)
    assert bridge.directives[-1]["op"] == "return"
    assert ("end", None) in kinds
    assert d.diagnostics()["active"] is False


def test_director_rejects_unknown_vocabulary_without_raising():
    bridge = FakeBridge()
    d = VisualDirector(bridge=bridge)
    errors = []
    d.bus.subscribe("visual_error", lambda e: errors.append(e.payload["reason"]))

    result = d.apply_intent({"subject": "apple", "material": "unobtainium"})
    assert "not available" in result       # spoken politely, voice continues
    assert len(bridge.directives) == 0     # nothing reached the renderer
    assert len(errors) == 1


def test_director_without_bridge_is_graceful():
    d = VisualDirector(bridge=None)
    result = d.apply_intent({"subject": "apple", "auto_return": False})
    assert "Visualising" in result
    assert d.available is False
    assert d.diagnostics()["active"] is True
    d.return_to_idle(d._generation)
    assert d.diagnostics()["active"] is False


def test_generation_guards_stale_returns():
    bridge = FakeBridge()
    d = VisualDirector(bridge=bridge)
    d.apply_intent({"subject": "apple", "auto_return": False})
    gen_old = d._generation
    d.apply_intent({"subject": "planet", "auto_return": False})
    d.return_to_idle(gen_old)              # stale return -> must be ignored
    assert "planet" in bridge.directives[-1]["subject"]
    assert d.diagnostics()["active"] is True
    d.return_to_idle(d._generation)        # current generation -> honoured
    assert bridge.directives[-1]["op"] == "return"


def test_singleton_set_get():
    set_visual_director(None)
    assert get_visual_director() is None
    d = VisualDirector(bridge=None)
    set_visual_director(d)
    assert get_visual_director() is d
    set_visual_director(None)


def test_auto_return_timer_fires():
    bridge = FakeBridge()
    d = VisualDirector(bridge=bridge)
    d.apply_intent({"subject": "sphere", "duration": 1, "auto_return": True})
    d.bus.subscribe("intent_end", lambda e: None)
    done = threading.Event()

    def _wait():
        deadline = 6.0
        while deadline > 0 and d.diagnostics()["active"]:
            deadline -= 0.02
            import time
            time.sleep(0.02)
        done.set()

    t = threading.Thread(target=_wait, daemon=True)
    t.start()
    assert done.wait(8), "auto-return never happened"
    assert d.diagnostics()["active"] is False
    assert bridge.directives[-1]["op"] == "return"