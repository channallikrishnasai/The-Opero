"""Visual intelligence subsystem (Phases 1-2: world model and intent schema)."""

from .concepts import (
    Concept,
    ConceptError,
    UnknownConceptError,
    VisualWorldError,
    load_concepts,
)
from .intent import (
    AnimationStyle,
    CameraPreset,
    EntityResolutionError,
    IntentAction,
    IntentMode,
    IntentValidationError,
    VisualIntent,
    resolve_entity_id,
)
from .world_model import (
    Entity,
    UnknownEntityError,
    UnknownPartError,
    VisualWorldModel,
)

__all__ = [
    "AnimationStyle",
    "CameraPreset",
    "Concept",
    "ConceptError",
    "Entity",
    "EntityResolutionError",
    "IntentAction",
    "IntentMode",
    "IntentValidationError",
    "UnknownConceptError",
    "UnknownEntityError",
    "UnknownPartError",
    "VisualIntent",
    "VisualWorldError",
    "VisualWorldModel",
    "load_concepts",
    "resolve_entity_id",
]
