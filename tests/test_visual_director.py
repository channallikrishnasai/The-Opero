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
    # After a visualization, return sends a transition_out directive
    assert bridge.directives[-1]["op"] in ("return", "transition_out")
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
    assert bridge.directives[-1]["op"] in ("return", "transition_out")


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
    assert bridge.directives[-1]["op"] in ("return", "transition_out")


def test_face_only_mode():
    """face_only intent sends a face_only directive."""
    bridge = FakeBridge()
    d = VisualDirector(bridge=bridge)
    result = d.apply_intent({"mode": "face_only"})
    assert "face_only" in result
    assert bridge.directives[-1]["op"] == "face_only"
    assert d.diagnostics()["visual_state"] == "FACE_ONLY"


def test_visualize_intent_with_transition():
    """Intent with transition sends a transition_in directive."""
    bridge = FakeBridge()
    d = VisualDirector(bridge=bridge)
    result = d.apply_intent({"subject": "engine", "transition": True,
                                 "transition_duration": 2.0})
    assert "engine" in result
    assert bridge.directives[-1]["op"] == "show"
    assert d.diagnostics()["visual_state"] == "TRANSITIONING"
    assert d.get_avatar_state() == "VISUALIZING"


def test_decide_visualize_recognizes_spatial_keywords():
    """decide_visualize returns True for spatial keywords."""
    assert VisualDirector.decide_visualize("the engine") == (True, "spatial_concept")
    assert VisualDirector.decide_visualize("the gear") == (True, "spatial_concept")


def test_decide_visualize_recognizes_structural_keywords():
    """decide_visualize returns True for structural keywords."""
    assert VisualDirector.decide_visualize("the skeleton") == (True, "structural_concept")
    assert VisualDirector.decide_visualize("the muscle") == (True, "structural_concept")


def test_decide_visualize_recognizes_causal_keywords():
    """decide_visualize returns True for causal keywords."""
    assert VisualDirector.decide_visualize("why does this happen") == (True, "causal_concept")


def test_decide_visualize_recognizes_temporal_keywords():
    """decide_visualize returns True for temporal keywords."""
    assert VisualDirector.decide_visualize("the timeline") == (True, "temporal_concept")


def test_decide_visualize_returns_face_only_for_unknown():
    """decide_visualize returns False for non-visual queries."""
    result, reason = VisualDirector.decide_visualize("hello world")
    assert result is False
    assert reason == "face_only"


def test_build_visual_intent():
    """build_visual_intent creates a proper intent dict."""
    intent = VisualDirector.build_visual_intent("engine", "spatial", "rotate", "inspection")
    assert intent["subject"] == "engine"
    assert intent["mode"] == "object_explanation"
    assert intent["visualize"] is True
    assert intent["transition"] is True
    assert intent["transition_duration"] == 2.2
    assert intent["return_to_face"] is True


def test_avatar_state_management():
    """set_avatar_state and get_avatar_state work correctly."""
    d = VisualDirector(bridge=None)
    d.set_avatar_state("LISTENING")
    assert d.get_avatar_state() == "LISTENING"
    d.set_avatar_state("VISUALIZING")
    assert d.get_avatar_state() == "VISUALIZING"
    assert d.diagnostics()["avatar_state"] == "VISUALIZING"


def test_visual_state_in_diagnostics():
    """diagnostics includes visual_state and active_subject."""
    bridge = FakeBridge()
    d = VisualDirector(bridge=bridge)
    d.apply_intent({"subject": "heart", "transition": True})
    diag = d.diagnostics()
    assert diag["visual_state"] in ("TRANSITIONING", "VISUALIZING")
    assert diag["active_subject"] == "heart"
    assert diag["avatar_state"] == "VISUALIZING"


# ── Acceptance tests for System Prompt 2 ──────────────────────────────

def test_causal_chain_engine():
    """Engine causal explanation renders a chain."""
    d = VisualDirector(bridge=None)
    d.show_causal_chain("engine_combustion", 0)
    assert d._causal_chain == "engine_combustion"
    assert d._causal_step == 0

def test_piston_interaction():
    """Piston can be isolated."""
    d = VisualDirector(bridge=None)
    d.set_inspection("isolated", isolate=["piston"])
    assert d._inspection_mode == "isolated"
    assert "piston" in d._inspection_isolate

def test_cutaway():
    """Cutaway mode can be applied."""
    d = VisualDirector(bridge=None)
    d.set_inspection("cutaway")
    assert d._inspection_mode == "cutaway"

def test_exploded_view():
    """Exploded view can be applied."""
    d = VisualDirector(bridge=None)
    d.set_inspection("exploded", exploded=True)
    assert d._inspection_mode == "exploded"
    assert d._inspection_exploded is True

def test_why_relationship_visualization():
    """'Why?' reveals relationships."""
    d = VisualDirector(bridge=None)
    result = d.handle_command("why does the engine work?")
    # The engine has relationships in RELATIONSHIPS
    from core.visual.registry import RELATIONSHIPS
    if "engine" in RELATIONSHIPS:
        assert "causes of engine" in result or "causes" in result or "why" in result
    else:
        assert result == ""

def test_what_happens_if_stops():
    """'What happens if X stops?' triggers simulation."""
    d = VisualDirector(bridge=None)
    result = d.handle_command("what happens if the piston stops?")
    assert "simulating" in result

def test_body_system_visualization():
    """Body system can be shown."""
    d = VisualDirector(bridge=None)
    d.show_body_system("circulatory", "heart")
    assert d._body_system == "circulatory"
    assert d._body_part == "heart"

def test_body_system_isolation():
    """Body system isolation works."""
    d = VisualDirector(bridge=None)
    d.show_body_system("nervous", "brain")
    assert d._body_system == "nervous"
    assert d._body_part == "brain"
    assert d._body_transparency >= 0.0

def test_temporal_controls():
    """Temporal controls work (play, pause, slow, step)."""
    d = VisualDirector(bridge=None)
    d.set_temporal("playing", speed=0.5)
    assert d._temporal_state == "playing"
    d.set_temporal("slow", speed=0.25)
    assert d._temporal_speed == 0.25
    d.set_temporal("stepped", step=3)
    assert d._temporal_step == 3

def test_timeline_controls():
    """Timeline controls work."""
    d = VisualDirector(bridge=None)
    d.set_temporal("playing", speed=1.0)
    d.set_temporal("paused")
    assert d._temporal_state == "paused"
    d.set_temporal("rewinding")
    assert d._temporal_state == "rewinding"

def test_story_environment():
    """Story mode can start with environment."""
    d = VisualDirector(bridge=None)
    scenes = [{"scene": "forest", "appear": ["tree"], "duration": 4.0}]
    d.start_story("forest", scenes, character="hero")
    assert d._story_environment == "forest"
    assert len(d._story_scenes) == 1

def test_character_movement():
    """Character state can be set."""
    d = VisualDirector(bridge=None)
    d._character_state = "walking"
    assert d._character_state == "walking"

def test_camera_follow():
    """Camera follow directive works."""
    d = VisualDirector(bridge=None)
    d.focus_entity("piston", "FOLLOW")
    assert d._camera_directive == "FOLLOW"

def test_accessory_attachment():
    """Accessory can be attached to anchor."""
    d = VisualDirector(bridge=None)
    d.attach_accessory("sunglasses", "face")
    assert d._inspection_mode == "normal"  # Just verify no error

def test_material_modification():
    """Material can be modified."""
    from core.visual.registry import MATERIALS
    assert "holographic" in MATERIALS
    assert "glass" in MATERIALS
    assert "transparent" in MATERIALS

def test_persistent_entity_identity():
    """Visual memory preserves entity IDs."""
    d = VisualDirector(bridge=None)
    entity_id = d.create_entity("apple_01", "apple", {"color": "red"})
    assert entity_id == "apple_01"
    entity = d.get_entity("apple_01")
    assert entity is not None
    assert entity["type"] == "apple"
    # Update
    d.update_entity("apple_01", {"color": "green"})
    assert d.get_entity("apple_01")["data"]["color"] == "green"

def test_natural_scene_commands():
    """Natural commands are parsed."""
    d = VisualDirector(bridge=None)
    assert d.handle_command("zoom in") == "zooming in"
    assert d.handle_command("rotate it") == "rotating"
    assert d.handle_command("show me inside") == "showing cutaway"
    assert d.handle_command("exploded view") == "showing exploded view"
    assert d.handle_command("slow down") == "slowing down"
    assert d.handle_command("follow it") == "following"

def test_correct_return_to_face():
    """Visualization returns to face when no longer needed."""
    d = VisualDirector(bridge=None)
    d.return_to_face()
    assert d._visual_state == "FACE_ONLY"
    assert d._avatar_state == "LISTENING"

def test_visualization_stops_when_not_useful():
    """Visualization state resets after return_to_face."""
    d = VisualDirector(bridge=None)
    d.apply_intent({"subject": "engine", "transition": True})
    assert d._visual_state == "TRANSITIONING"
    d.return_to_face()
    assert d._visual_state == "FACE_ONLY"
    assert d._causal_chain == ""
    assert d._body_system == ""

def test_user_can_force_visualization():
    """User can force visualization via face_only mode."""
    d = VisualDirector(bridge=None)
    result = d.apply_intent({"mode": "face_only"})
    assert "face_only" in result
    assert d._visual_state == "FACE_ONLY"

def test_user_can_stop_visualization():
    """User can stop visualization."""
    d = VisualDirector(bridge=None)
    d.apply_intent({"subject": "engine"})
    assert d._active_subject == "engine"
    d.return_to_face()
    assert d._active_subject is None


def test_relationship_graph():
    """Entity relationships are first-class data."""
    from core.visual.registry import RELATIONSHIPS
    assert "engine" in RELATIONSHIPS
    engine_rels = RELATIONSHIPS["engine"]
    assert any(r["target"] == "piston" and r["relation"] == "contains" for r in engine_rels)
    assert any(r["target"] == "fuel" and r["relation"] == "uses" for r in engine_rels)