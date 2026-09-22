"""Typed visual intent and its hard validator.

Gemini never talks to the renderer directly.  It may only request things that
fit the controlled vocabulary in `core.visual.registry`, and `validate_intent`
turns a raw dict into a typed :class:`VisualIntent` — rejecting unknown
objects, materials, camera modes, anchors, malformed colours and oversized
scenes.  Anything that fails simply gets a graceful message; the voice
response always continues.

This is the security boundary of the visual layer: NOTHING arbitrary (code,
paths, commands, unbounded resources) can pass through it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.visual.registry import (
    ACCESSORY_ANCHOR,
    ANCHORS,
    ANIMATIONS,
    CAMERA_MODES,
    ENVIRONMENTS,
    INTERIOR_TOKENS,
    LIMITS,
    MATERIALS,
    MODES,
    OBJECTS,
    SEMANTIC_COLORS,
)

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_TOKEN_RE = re.compile(r"^[a-z0-9_]{1,32}$")


class VisualError(ValueError):
    """Raised when a visual intent fails validation (human-readable message)."""


@dataclass
class VisualIntent:
    """A validated, renderer-agnostic visual request."""

    mode: str = "object_explanation"
    subject: str = ""                       # object id (registry) or free label
    material: str = "holographic"
    color: str = ""                         # resolved hex, or "" -> semantic default
    animation: str = "rotate"
    camera: str = "default"
    environment: str = "minimal"
    duration: float = 8.0                   # seconds the focus scene lasts
    orbit: bool = False
    zoom: bool = True
    particle_scale: float = 1.0
    highlight: list[str] = field(default_factory=list)
    attach: str = ""                        # anchor id for accessories
    story: list[dict] | None = None         # constrained scene list
    auto_return: bool = True                # dissolve back to avatar afterwards

    @property
    def object_id(self) -> str:
        """The registry id for the primary subject ('' if unknown/freeform)."""
        return self.subject if self.subject in OBJECTS else ""


def _resolve_color(raw: Any) -> str:
    if raw is None or raw == "":
        return ""
    value: str = str(raw).strip().lower()
    if value in SEMANTIC_COLORS:
        return SEMANTIC_COLORS[value]
    if _HEX_RE.match(value):
        return value.lower()
    raise VisualError(f"unknown colour '{raw}' (use a named token or #rrggbb)")


def _check_list(raw: Any, name: str, allowed: tuple | frozenset, lower: bool = True):
    if isinstance(raw, (list, tuple)):
        return [str(x).strip().lower() if lower else str(x).strip() for x in raw]
    if isinstance(raw, str):
        return [s.strip().lower() if lower else s.strip()
                for s in raw.replace(";", ",").split(",") if s.strip()]
    raise VisualError(f"'{name}' must be a list of names")


def _validate_story(value: Any) -> list[dict] | None:
    """Story is a *bounded* list of scenes, each a small constrained dict.

    Scene shape::
        {"scene": "<environment>", "appear": ["tree", ...], "remove": [...],
         "duration": 3.0}            # duration optional, 1..15s
    """
    if value is None or value == "":
        return None
    if isinstance(value, str):
        import json as _json
        try:
            value = _json.loads(value)
        except Exception:
            raise VisualError("story must be valid JSON text or a list")
    if not isinstance(value, list) or not value:
        raise VisualError("story must be a non-empty list of scenes")
    if len(value) > LIMITS["story_scenes_max"]:
        raise VisualError(f"story supports at most {int(LIMITS['story_scenes_max'])} scenes")

    out: list[dict] = []
    for scene in value:
        if not isinstance(scene, dict):
            raise VisualError("each story scene must be an object")
        s: dict[str, Any] = {"scene": "minimal", "appear": [], "remove": [],
                             "duration": 4.0}
        env = str(scene.get("scene", "minimal") or "minimal").strip().lower()
        if env not in ENVIRONMENTS:
            raise VisualError(f"unknown story scene '{scene.get('scene')}'")
        s["scene"] = env
        for key in ("appear", "remove"):
            items = _check_list(scene.get(key, []), f"story.{key}", OBJECTS)
            if len(items) > LIMITS["story_objects_max"]:
                raise VisualError(f"story.{key} supports at most "
                                  f"{int(LIMITS['story_objects_max'])} objects")
            for obj in items:
                if obj not in OBJECTS:
                    raise VisualError(f"unknown story object '{obj}'")
            s[key] = items
        try:
            dur = float(scene.get("duration", 4.0) or 4.0)
        except (TypeError, ValueError):
            raise VisualError("story scene duration must be a number")
        s["duration"] = min(max(dur, 1.0), 15.0)
        out.append(s)
    return out


def validate_intent(raw: dict) -> VisualIntent:
    """Validate a raw intent dict into a typed :class:`VisualIntent`.

    Raises :class:`VisualError` with a human-readable message on any problem.
    """
    if not isinstance(raw, dict):
        raise VisualError("visual intent must be an object")

    mode = str(raw.get("mode") or "object_explanation").strip().lower()
    if mode not in MODES:
        raise VisualError(f"unknown mode '{raw.get('mode')}' (choose from {', '.join(MODES)})")

    subject = str(raw.get("subject") or "").strip()
    if len(subject) > LIMITS["subject_len_max"]:
        raise VisualError(f"subject is too long (max {int(LIMITS['subject_len_max'])} chars)")

    material = str(raw.get("material") or "holographic").strip().lower()
    if material not in MATERIALS:
        raise VisualError(f"unknown material '{raw.get('material')}'")

    animation = str(raw.get("animation") or "rotate").strip().lower()
    if animation not in ANIMATIONS:
        raise VisualError(f"unknown animation '{raw.get('animation')}'")

    camera = str(raw.get("camera") or "default").strip().lower()
    if camera not in CAMERA_MODES:
        raise VisualError(f"unknown camera mode '{raw.get('camera')}'")

    environment = str(raw.get("environment") or "minimal").strip().lower()
    if environment not in ENVIRONMENTS:
        raise VisualError(f"unknown environment '{raw.get('environment')}'")

    color = _resolve_color(raw.get("color"))

    try:
        duration = float(raw.get("duration") or 8.0)
    except (TypeError, ValueError):
        raise VisualError("duration must be a number (seconds)")
    if duration < LIMITS["duration_min"] or duration > LIMITS["duration_max"]:
        raise VisualError(f"duration must be between {LIMITS['duration_min']} and "
                          f"{LIMITS['duration_max']} seconds")

    try:
        particle_scale = float(raw.get("particle_scale") or 1.0)
    except (TypeError, ValueError):
        raise VisualError("particle_scale must be a number")
    if particle_scale <= 0 or particle_scale > LIMITS["particle_scale_max"]:
        raise VisualError(f"particle_scale must be between 0 and "
                          f"{LIMITS['particle_scale_max']}")

    highlights = _check_list(raw.get("highlight", []), "highlight", frozenset())
    if len(highlights) > LIMITS["highlight_max"]:
        raise VisualError(f"highlight supports at most {int(LIMITS['highlight_max'])} items")
    for h in highlights:
        if not _TOKEN_RE.match(h):
            raise VisualError(f"invalid highlight token '{h}'")

    attach = str(raw.get("attach") or "").strip().lower()
    if attach and attach not in ANCHORS:
        raise VisualError(f"unknown attachment point '{raw.get('attach')}'")
    if mode == "accessory":
        if not subject:
            raise VisualError("accessory mode requires a subject")
        if subject not in OBJECTS:
            raise VisualError(f"unknown accessory object '{subject}'")
        if not attach:
            attach = ACCESSORY_ANCHOR.get(subject, "")

    story = _validate_story(raw.get("story"))

    orbit = bool(raw.get("orbit", False))
    if raw.get("zoom") is not None:
        zoom = bool(raw.get("zoom"))
    else:
        zoom = True
    auto_return = bool(raw.get("auto_return", True))

    return VisualIntent(
        mode=mode, subject=subject, material=material, color=color,
        animation=animation, camera=camera, environment=environment,
        duration=duration, orbit=orbit, zoom=zoom,
        particle_scale=particle_scale, highlight=highlights, attach=attach,
        story=story, auto_return=auto_return,
    )


def build_intent(raw: dict) -> VisualIntent:
    """Alias used by the visualizer action (validate with a friendly error)."""
    return validate_intent(raw)


def intent_to_directive(intent: VisualIntent) -> dict:
    """Translate a validated intent into the compact renderer directive.

    The directive is pure data (strings/numbers/lists from the vocabulary); the
    renderer is the only place allowed to interpret it.
    """
    semantic = OBJECTS.get(intent.subject, {}).get("semantic", "#00d4ff") \
        if intent.subject in OBJECTS else "#00d4ff"
    color = intent.color or (semantic if intent.subject else "#00d4ff")
    known = intent.subject if intent.subject in OBJECTS else "sphere"

    interior = known in OBJECTS and OBJECTS[known].get("interior") \
        and any(tok in intent.highlight for tok in INTERIOR_TOKENS)

    return {
        "op": "show",
        "mode": intent.mode,
        "subject": known,
        "material": intent.material,
        "color": color,
        "animation": intent.animation,
        "camera": intent.camera,
        "environment": intent.environment,
        "duration": round(intent.duration, 2),
        "orbit": bool(intent.orbit),
        "zoom": bool(intent.zoom),
        "particle_scale": round(intent.particle_scale, 3),
        "highlight": list(intent.highlight),
        "interior": bool(interior),
        "attach": intent.attach or (ACCESSORY_ANCHOR.get(intent.subject, "")
                                    if intent.mode == "accessory" else ""),
        "story": intent.story,
        "auto_return": bool(intent.auto_return),
    }