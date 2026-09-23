"""Visual intelligence layer for OPERO.

The vision: the 3D environment becomes a first-class communication channel.
Gemini speaks a *controlled vocabulary* (core/visual/registry.py), a validator
turns that into a typed VisualIntent (core/visual/intent.py), and the
VisualDirector (core/visual/director.py) translates it into constrained
renderer directives. No generated JavaScript can ever reach the renderer.

Package layout follows the codebase convention of small, single-purpose core
modules:

    registry.py  — the controlled vocabulary (objects, materials, cameras, …)
    intent.py    — typed intent dataclass + hard schema validation
    events.py    — tiny event bus (decouples director / UI / tests)
    assets.py    — head geometry + anchor payloads for the 3D renderer
    director.py  — validates intent, drives the renderer bridge, falls back
"""
from __future__ import annotations

from core.visual.events import VisualBus, VisualEvent
from core.visual.intent import (
    VisualError,
    VisualIntent,
    build_intent,
    intent_to_directive,
    validate_intent,
)
from core.visual.director import (
    VisualDirector,
    get_visual_director,
    set_visual_director,
    setup_visual_system,
)
from core.visual.assets import FACE_ANCHORS, face_mesh_payload
from core.visual.registry import (
    MODES, OBJECTS, MATERIALS, CAMERA_MODES, ANIMATIONS,
    ENVIRONMENTS, SEMANTIC_COLORS, ANCHORS,
    BODY_PARTS, RELATIONSHIPS, CAUSAL_CHAINS,
    INSPECTION_MODES, TEMPORAL_STATES, CAMERA_DIRECTIVES,
    CHARACTER_STATES, BODY_SYSTEMS, ACCESSORY_ANCHOR,
    INTERIOR_TOKENS, LIMITS,
)

__all__ = [
    "VisualBus",
    "VisualEvent",
    "VisualError",
    "VisualIntent",
    "build_intent",
    "intent_to_directive",
    "validate_intent",
    "VisualDirector",
    "get_visual_director",
    "set_visual_director",
    "setup_visual_system",
    "FACE_ANCHORS",
    "face_mesh_payload",
    "MODES",
    "OBJECTS",
    "MATERIALS",
    "CAMERA_MODES",
    "ANIMATIONS",
    "ENVIRONMENTS",
    "SEMANTIC_COLORS",
    "ANCHORS",
    "BODY_PARTS",
    "RELATIONSHIPS",
    "CAUSAL_CHAINS",
    "INSPECTION_MODES",
    "TEMPORAL_STATES",
    "CAMERA_DIRECTIVES",
    "CHARACTER_STATES",
    "BODY_SYSTEMS",
    "ACCESSORY_ANCHOR",
    "INTERIOR_TOKENS",
    "LIMITS",
]