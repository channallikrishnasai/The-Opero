"""Visual-intent validator: the security boundary of the visual layer.

These tests pin down the controlled vocabulary — what Gemini may ask the
renderer to do, and what must ALWAYS be rejected (unknown vocabulary, missing
accessory subjects, malformed colours, oversized scenes, anything code-like).
"""

from __future__ import annotations

import pytest

from core.visual.intent import (
    VisualError,
    intent_to_directive,
    validate_intent,
)


def test_valid_object_explanation():
    intent = validate_intent({
        "mode": "object_explanation",
        "subject": "apple",
        "material": "holographic",
        "color": "apple_red",
        "animation": "rotate",
        "camera": "focus",
        "duration": 6,
        "highlight": ["core", "seeds"],
    })
    assert intent.subject == "apple"
    assert intent.color == "#ff3045"
    assert intent.duration == 6.0
    d = intent_to_directive(intent)
    assert d["op"] == "show"
    assert d["subject"] == "apple"
    assert d["interior"] is True          # highlight contains an interior token
    assert d["material"] == "holographic"
    assert d["camera"] == "focus"


def test_semantic_color_and_hex():
    assert validate_intent({"subject": "apple", "color": "gold"}).color == "#ffc94d"
    assert validate_intent({"subject": "apple", "color": "#12abEF"}).color == "#12abef"


def test_unknown_vocabulary_rejected():
    for raw in (
        {"subject": "apple", "material": "magnetic"},
        {"subject": "apple", "animation": "teleport"},
        {"subject": "apple", "camera": "spycam"},
        {"subject": "apple", "environment": "volcano"},
        {"subject": "apple", "mode": "holodeck"},
        {"subject": "apple", "attach": "tentacle"},
        {"subject": "apple", "color": "chartreuse-9"},
    ):
        with pytest.raises(VisualError):
            validate_intent(raw)


def test_bounds_are_hard():
    with pytest.raises(VisualError):
        validate_intent({"subject": "apple", "duration": 0.2})
    with pytest.raises(VisualError):
        validate_intent({"subject": "apple", "duration": 9999})
    with pytest.raises(VisualError):
        validate_intent({"subject": "x" * 200})
    with pytest.raises(VisualError):
        validate_intent({"subject": "apple", "highlight": ["a", "b", "c", "d", "e", "f", "g", "h", "i"]})


def test_accessory_requires_known_subject_and_anchor_defaults():
    with pytest.raises(VisualError):
        validate_intent({"mode": "accessory"})
    with pytest.raises(VisualError):
        validate_intent({"mode": "accessory", "subject": "raygun"})
    intent = validate_intent({"mode": "accessory", "subject": "sunglasses", "color": "gold"})
    assert intent.attach == "face"
    intent = validate_intent({"mode": "accessory", "subject": "watch"})
    assert intent.attach == "left_wrist"


def test_story_is_bounded_and_validated():
    story = [
        {"scene": "forest", "appear": ["tree", "tree"], "duration": 3},
        {"scene": "desert", "appear": ["tree"], "remove": []},
    ]
    intent = validate_intent({"mode": "story", "subject": "story_scene", "story": story})
    assert intent.story[0]["scene"] == "forest"

    with pytest.raises(VisualError):
        validate_intent({"mode": "story", "story": [{"scene": "underwater"}]})
    with pytest.raises(VisualError):
        validate_intent({"mode": "story",
                         "story": [{"scene": "forest", "appear": ["x" * 9]}]})
    with pytest.raises(VisualError):
        validate_intent({"mode": "story",
                         "story": [{"scene": "forest"}] * 9})   # > 8 scenes
    with pytest.raises(VisualError):
        validate_intent({"mode": "story", "story": "not json {"})


def test_unknown_subject_falls_back_to_safe_primitive():
    # Free labels are allowed as subjects, but the renderer directive must
    # always carry a known builder id — never the raw model string.
    intent = validate_intent({"subject": "some random guitar", "mode": "object_explanation"})
    assert intent.subject == "some random guitar"     # kept for speech context
    d = intent_to_directive(intent)
    assert d["subject"] == "sphere"
    assert d["op"] == "show"


def test_non_dict_rejected():
    with pytest.raises(VisualError):
        validate_intent("make me a thing")


def test_boolean_extras():
    intent = validate_intent({"subject": "planet", "orbit": True, "zoom": False,
                              "auto_return": False})
    assert intent.orbit is True
    assert intent.zoom is False
    assert intent.auto_return is False