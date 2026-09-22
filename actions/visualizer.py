"""visualize — the ONLY path from Gemini to the 3D renderer.

Gemini requests a visualisation with plain data (an object id, a material, a
camera mode), never with code.  The handler validates the request against the
controlled vocabulary in core/visual/registry.py and hands the resulting
directive to the VisualDirector, which drives the THREE.js scene.

Safety: visual intent is NOT authorisation.  This action only ever shows
things; destructive actions still go through OPERO's normal confirmation gate.
"""

from __future__ import annotations

import json

from core.logger import get_logger

log = get_logger(__name__)


def visualize(parameters, **_kwargs) -> str:
    """Validated entry point called by the action dispatcher."""
    from core.visual.director import get_visual_director

    director = get_visual_director()
    if director is None:
        return "Visualisation is not available on this system."

    intent = dict(parameters or {})

    # The Live API model may hand the story back as JSON text rather than a
    # nested list; normalise it before validation (validation still rejects
    # unknown scenes/objects — this is not a bypass).
    story = intent.get("story")
    if isinstance(story, str) and story.strip():
        try:
            intent["story"] = json.loads(story)
        except Exception:
            intent["story"] = None
            log.warning("visualize: story JSON unreadable — ignored")

    return director.apply_intent(intent)


TOOL = {
    "name": "visualize",
    "description": (
        "Show a real 3D holographic visualisation of what you are talking about. "
        "Use when the user asks to SEE something or explaining an object, a place, "
        "an accessory, a process or a story and a 3D scene would genuinely help "
        "(e.g. 'what is an apple', 'show me the inside of an apple', 'show me "
        "sunglasses', 'make them gold', 'how does the solar system work', 'tell me "
        "a story'). Do NOT call for plain conversation, greetings or text-only "
        "answers. Parameters follow a controlled vocabulary: subject must be one "
        "of the known objects (apple, sphere, cube, torus, cone, cylinder, "
        "capsule, icosa, planet, sun, moon, sunglasses, watch, ring, necklace, "
        "hat, tree, ground); material one of (holographic, glass, metal, matte, "
        "emissive, particle, transparent); camera one of (default, portrait, "
        "focus, orbit, zoom, closeup, wide, top_down, side, inspection, "
        "cinematic, follow); animation one of (rotate, assemble, dissolve, "
        "pulse, orbit, bounce, highlight, scan, float, idle); mode one of "
        "(object_explanation, accessory, story, process, diagram, data, "
        "system_action, transition); color is a named token (gold, red, green, "
        "blue, cyan, white, black, violet, orange, ocean, earth, warning) or a "
        "#rrggbb hex. highlight lists parts of the object to emphasise (use "
        "'core', 'inside', 'seeds' or 'cutaway' to reveal the inside for apple "
        "and planet). For accessories set mode=accessory; attach defaults to the "
        "object's natural anchor (sunglasses->face, watch->left_wrist, "
        "ring->left_index, necklace->neck, hat->head). For a story pass story as "
        "JSON text: [{\"scene\":\"forest\",\"appear\":[\"tree\"],\"remove\":[],"
        "\"duration\":4}, ...] with scene being an environment (minimal, space, "
        "forest, desert, city, ocean)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "subject": {"type": "STRING", "description": "Object to visualise (registry id or short label)."},
            "mode": {"type": "STRING", "description": "object_explanation | accessory | story | process | diagram | data | system_action | transition"},
            "material": {"type": "STRING", "description": "holographic | glass | metal | matte | emissive | particle | transparent"},
            "color": {"type": "STRING", "description": "Named semantic colour or #rrggbb hex"},
            "animation": {"type": "STRING", "description": "rotate | assemble | dissolve | pulse | orbit | bounce | highlight | scan | float | idle"},
            "camera": {"type": "STRING", "description": "default | portrait | focus | orbit | zoom | closeup | wide | top_down | side | inspection | cinematic | follow"},
            "environment": {"type": "STRING", "description": "minimal | space | forest | desert | city | ocean"},
            "duration": {"type": "NUMBER", "description": "Seconds the focus scene lasts (1-120, default 8)"},
            "orbit": {"type": "BOOLEAN", "description": "Orbit the camera as it shows the object"},
            "attach": {"type": "STRING", "description": "Body anchor for accessories (face, left_wrist, ...)"},
            "highlight": {"type": "STRING", "description": "Comma-separated part names to emphasise (core, inside, seeds, cutaway, ...)"},
            "story": {"type": "STRING", "description": "JSON text list of story scenes for mode=story"},
            "auto_return": {"type": "BOOLEAN", "description": "Dissolve back to the avatar when the explanation ends (default true)"},
        },
        "required": ["subject"],
    },
    "handler": visualize,
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
}