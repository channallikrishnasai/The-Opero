"""Renderer-independent Visual Intent: the semantic contract between reasoning and the visual runtime.

Phase 2 of the visual subsystem. An intent says WHAT should happen and never
contains executable content (no JavaScript, shaders, Three.js snippets, or
eval'able Python) and never references a renderer. The future Visual Director
decides HOW to execute an intent; the World Model owns WHAT currently exists.
"""

import json
from copy import deepcopy
from dataclasses import dataclass, field, fields
from enum import StrEnum
from typing import Any, TypeVar

from .concepts import VisualWorldError
from .world_model import UnknownEntityError, VisualWorldModel


class IntentValidationError(VisualWorldError):
    """Raised when a visual intent is malformed or combines invalid values."""


class EntityResolutionError(VisualWorldError):
    """Raised when an intent's target cannot be resolved to an existing entity."""


class IntentMode(StrEnum):
    FACE_ONLY = "face_only"
    OBJECT = "object"
    OBJECT_INSPECTION = "object_inspection"
    PROCESS = "process"
    CAUSAL_CHAIN = "causal_chain"
    INSTRUCTION = "instruction"


class IntentAction(StrEnum):
    SHOW = "show"
    HIDE = "hide"
    FOCUS = "focus"
    ZOOM = "zoom"
    ROTATE = "rotate"
    MOVE = "move"
    HIGHLIGHT = "highlight"
    ISOLATE = "isolate"
    CUTAWAY = "cutaway"
    RETURN_TO_FACE = "return_to_face"
    PAUSE = "pause"
    RESUME = "resume"
    REPLAY = "replay"
    SLOW = "slow"


class CameraPreset(StrEnum):
    DEFAULT = "default"
    FOCUS = "focus"
    ZOOM = "zoom"
    ORBIT = "orbit"
    CLOSEUP = "closeup"
    WIDE = "wide"
    INSPECTION = "inspection"
    SIDE = "side"
    TOP_DOWN = "top_down"


class AnimationStyle(StrEnum):
    NONE = "none"
    APPEAR = "appear"
    DISAPPEAR = "disappear"
    ROTATE = "rotate"
    MOVE = "move"
    HIGHLIGHT = "highlight"
    PULSE = "pulse"
    ASSEMBLE = "assemble"
    DISASSEMBLE = "disassemble"
    EXPLODE = "explode"
    IMPLODE = "implode"


# Actions that act on a visual object: they require a target and are meaningless in FACE_ONLY.
_OBJECT_ACTIONS = frozenset(
    {
        IntentAction.SHOW,
        IntentAction.HIDE,
        IntentAction.FOCUS,
        IntentAction.ZOOM,
        IntentAction.ROTATE,
        IntentAction.MOVE,
        IntentAction.HIGHLIGHT,
        IntentAction.ISOLATE,
        IntentAction.CUTAWAY,
    }
)

_E = TypeVar("_E", bound=StrEnum)


def _coerce_enum(enum_cls: type[_E], value: object, field_name: str) -> _E:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value.lower())
        except ValueError:
            pass
    options = [member.value for member in enum_cls]
    raise IntentValidationError(f"invalid {field_name} {value!r}; valid values: {options}")


@dataclass(kw_only=True)
class VisualIntent:
    """A validated, deterministic, renderer-independent visual instruction."""

    mode: IntentMode = IntentMode.OBJECT
    action: IntentAction
    concept_id: str | None = None
    entity_id: str | None = None
    camera: CameraPreset = CameraPreset.DEFAULT
    animation: AnimationStyle = AnimationStyle.NONE
    target_part: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    narration_sync: bool = False

    def __post_init__(self) -> None:
        self.mode = _coerce_enum(IntentMode, self.mode, "mode")
        self.action = _coerce_enum(IntentAction, self.action, "action")
        self.camera = _coerce_enum(CameraPreset, self.camera, "camera")
        self.animation = _coerce_enum(AnimationStyle, self.animation, "animation")
        if not isinstance(self.parameters, dict):
            raise IntentValidationError(f"parameters must be a dict, got {type(self.parameters).__name__}")
        try:
            json.dumps(self.parameters)
        except (TypeError, ValueError) as exc:
            raise IntentValidationError(f"parameters must be JSON-serializable: {exc}") from exc
        if not isinstance(self.narration_sync, bool):
            raise IntentValidationError(f"narration_sync must be a bool, got {type(self.narration_sync).__name__}")
        for name in ("concept_id", "entity_id", "target_part"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise IntentValidationError(f"{name} must be a non-empty string or None, got {value!r}")
        self._validate_combinations()

    def _validate_combinations(self) -> None:
        if self.mode is IntentMode.FACE_ONLY and self.action in _OBJECT_ACTIONS:
            raise IntentValidationError(f"{self.action.value!r} is not allowed in FACE_ONLY mode")
        if self.action in _OBJECT_ACTIONS and not (self.entity_id or self.concept_id):
            raise IntentValidationError(f"{self.action.value!r} requires a target: entity_id or concept_id")
        if self.entity_id and self.concept_id:
            prefix, separator, tail = self.entity_id.rpartition("_")
            if separator and tail.isdigit() and prefix != self.concept_id:
                raise IntentValidationError(
                    f"entity_id {self.entity_id!r} does not belong to concept {self.concept_id!r}"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "action": self.action.value,
            "concept_id": self.concept_id,
            "entity_id": self.entity_id,
            "camera": self.camera.value,
            "animation": self.animation.value,
            "target_part": self.target_part,
            "parameters": deepcopy(self.parameters),
            "narration_sync": self.narration_sync,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualIntent":
        if not isinstance(data, dict):
            raise IntentValidationError(f"intent payload must be a dict, got {type(data).__name__}")
        known_fields = {spec.name for spec in fields(cls)}
        unknown = set(data) - known_fields
        if unknown:
            raise IntentValidationError(f"unknown intent fields: {sorted(str(item) for item in unknown)}")
        if "action" not in data:
            raise IntentValidationError("intent payload missing required field 'action'")
        return cls(
            mode=data.get("mode", IntentMode.OBJECT),
            action=data["action"],
            concept_id=data.get("concept_id"),
            entity_id=data.get("entity_id"),
            camera=data.get("camera", CameraPreset.DEFAULT),
            animation=data.get("animation", AnimationStyle.NONE),
            target_part=data.get("target_part"),
            parameters=data.get("parameters", {}),
            narration_sync=data.get("narration_sync", False),
        )


def resolve_entity_id(intent: VisualIntent, world: VisualWorldModel) -> str:
    """Resolve the intent's target to an existing entity id; never invents entities."""
    if intent.entity_id is not None:
        try:
            world.get_entity(intent.entity_id)
        except UnknownEntityError as exc:
            raise EntityResolutionError(f"entity {intent.entity_id!r} does not exist in the world model") from exc
        return intent.entity_id
    if intent.concept_id is not None:
        live = sorted(entity["id"] for entity in world.to_dict()["entities"] if entity["concept"] == intent.concept_id)
        if live:
            return live[0]
        raise EntityResolutionError(f"no live entity for concept {intent.concept_id!r}")
    raise EntityResolutionError(f"{intent.action.value!r} intent has no entity_id or concept_id to resolve")
