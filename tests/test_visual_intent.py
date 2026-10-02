"""Tests for the Visual Intent schema (Phase 2)."""

import pytest

from core.visual import (
    AnimationStyle,
    CameraPreset,
    EntityResolutionError,
    IntentAction,
    IntentMode,
    IntentValidationError,
    VisualIntent,
    VisualWorldModel,
    resolve_entity_id,
)


def test_valid_show_intent() -> None:
    intent = VisualIntent(action=IntentAction.SHOW, concept_id="apple")
    assert intent.mode is IntentMode.OBJECT
    assert intent.action is IntentAction.SHOW
    assert intent.concept_id == "apple"
    assert intent.entity_id is None


def test_valid_rotate_intent() -> None:
    intent = VisualIntent(action=IntentAction.ROTATE, entity_id="apple_01")
    assert intent.mode is IntentMode.OBJECT
    assert intent.action is IntentAction.ROTATE
    assert intent.entity_id == "apple_01"
    assert intent.concept_id is None


def test_valid_focus_intent() -> None:
    intent = VisualIntent(action=IntentAction.FOCUS, entity_id="apple_01", target_part="stem")
    assert intent.action is IntentAction.FOCUS
    assert intent.target_part == "stem"


def test_valid_cutaway_intent() -> None:
    intent = VisualIntent(mode=IntentMode.OBJECT_INSPECTION, action=IntentAction.CUTAWAY, entity_id="apple_01")
    assert intent.mode is IntentMode.OBJECT_INSPECTION
    assert intent.action is IntentAction.CUTAWAY


def test_valid_return_to_face() -> None:
    intent = VisualIntent(mode=IntentMode.FACE_ONLY, action=IntentAction.RETURN_TO_FACE)
    assert intent.mode is IntentMode.FACE_ONLY
    assert intent.action is IntentAction.RETURN_TO_FACE
    assert intent.concept_id is None
    assert intent.entity_id is None


def test_invalid_mode_rejected() -> None:
    with pytest.raises(IntentValidationError, match="invalid mode"):
        VisualIntent(mode="HOLOGRAM", action=IntentAction.SHOW, concept_id="apple")


def test_invalid_action_rejected() -> None:
    with pytest.raises(IntentValidationError, match="invalid action"):
        VisualIntent(action="TELEPORT", concept_id="apple")


def test_rotate_without_target_rejected() -> None:
    with pytest.raises(IntentValidationError, match="requires a target"):
        VisualIntent(action=IntentAction.ROTATE)


def test_focus_without_target_rejected() -> None:
    with pytest.raises(IntentValidationError, match="requires a target"):
        VisualIntent(action=IntentAction.FOCUS, target_part="stem")


def test_cutaway_in_face_only_rejected() -> None:
    with pytest.raises(IntentValidationError, match="not allowed in FACE_ONLY"):
        VisualIntent(mode=IntentMode.FACE_ONLY, action=IntentAction.CUTAWAY, entity_id="apple_01")


def test_invalid_parameter_type_rejected() -> None:
    with pytest.raises(IntentValidationError, match="JSON-serializable"):
        VisualIntent(action=IntentAction.ZOOM, entity_id="apple_01", parameters={"speed": object()})


def test_serialization_round_trip() -> None:
    intent = VisualIntent(
        mode=IntentMode.OBJECT_INSPECTION,
        action=IntentAction.CUTAWAY,
        entity_id="apple_01",
        camera=CameraPreset.INSPECTION,
        animation=AnimationStyle.DISASSEMBLE,
        target_part="stem",
        parameters={"angle": 45.0},
        narration_sync=True,
    )
    restored = VisualIntent.from_dict(intent.to_dict())
    assert restored == intent
    assert restored.to_dict() == intent.to_dict()
    assert isinstance(restored.mode, IntentMode)
    assert isinstance(restored.camera, CameraPreset)


def test_malformed_serialized_intent_rejected() -> None:
    with pytest.raises(IntentValidationError, match="must be a dict"):
        VisualIntent.from_dict(["not", "a", "dict"])  # type: ignore[arg-type]
    with pytest.raises(IntentValidationError, match="missing required field 'action'"):
        VisualIntent.from_dict({"mode": "object"})
    with pytest.raises(IntentValidationError, match="unknown intent fields"):
        VisualIntent.from_dict({"action": "show", "concept_id": "apple", "renderer": "three.js"})


def test_concept_entity_distinction() -> None:
    show = VisualIntent(action=IntentAction.SHOW, concept_id="apple")
    assert show.concept_id == "apple"
    assert show.entity_id is None

    rotate = VisualIntent(action=IntentAction.ROTATE, entity_id="apple_01")
    assert rotate.entity_id == "apple_01"
    assert rotate.concept_id is None

    with pytest.raises(IntentValidationError, match="does not belong to concept"):
        VisualIntent(action=IntentAction.ROTATE, concept_id="apple", entity_id="banana_01")


def test_camera_validation() -> None:
    intent = VisualIntent(action=IntentAction.SHOW, concept_id="apple", camera="orbit")
    assert intent.camera is CameraPreset.ORBIT

    with pytest.raises(IntentValidationError, match="invalid camera"):
        VisualIntent(action=IntentAction.SHOW, concept_id="apple", camera="sideways")


def test_animation_validation() -> None:
    intent = VisualIntent(action=IntentAction.SHOW, concept_id="apple", animation="explode")
    assert intent.animation is AnimationStyle.EXPLODE

    with pytest.raises(IntentValidationError, match="invalid animation"):
        VisualIntent(action=IntentAction.SHOW, concept_id="apple", animation="twerk")


def test_resolve_existing_entity() -> None:
    world = VisualWorldModel()
    world.create_entity("apple")
    intent = VisualIntent(action=IntentAction.ROTATE, entity_id="apple_01")
    assert resolve_entity_id(intent, world) == "apple_01"


def test_resolve_concept_to_live_entity() -> None:
    world = VisualWorldModel()
    world.create_entity("apple")
    intent = VisualIntent(action=IntentAction.SHOW, concept_id="apple")
    assert resolve_entity_id(intent, world) == "apple_01"


def test_resolve_missing_entity_errors() -> None:
    world = VisualWorldModel()
    intent = VisualIntent(action=IntentAction.ROTATE, entity_id="apple_01")
    with pytest.raises(EntityResolutionError, match="does not exist"):
        resolve_entity_id(intent, world)


def test_resolve_missing_concept_errors_without_inventing() -> None:
    world = VisualWorldModel()
    intent = VisualIntent(action=IntentAction.SHOW, concept_id="apple")
    with pytest.raises(EntityResolutionError, match="no live entity"):
        resolve_entity_id(intent, world)
    assert world.to_dict()["entities"] == []


def test_resolve_without_target_errors() -> None:
    world = VisualWorldModel()
    intent = VisualIntent(mode=IntentMode.FACE_ONLY, action=IntentAction.RETURN_TO_FACE)
    with pytest.raises(EntityResolutionError, match="no entity_id or concept_id"):
        resolve_entity_id(intent, world)
