"""The controlled vocabulary of the visual system.

This module is the single source of truth for what Gemini may ask OPERO to
visualise.  EVERYTHING here is a whitelist: unknown tokens are rejected before
they ever reach the renderer.  The JavaScript side interprets these ids and is
the only place that knows how to build each object — no code is ever generated
between them.

Adding a new object/asset is therefore a two-sided, config-only change:
  * add its id here (Python side), and
  * teach `site/web_background/avatar3d.js` to build it.
"""

from __future__ import annotations

# ── Visual modes ─────────────────────────────────────────────────────────────
MODES: tuple[str, ...] = (
    "object_explanation",   # an object is shown, described, transformed
    "accessory",            # an object attaches to a body anchor
    "story",                # a sequence of scenes with an environment
    "process",              # ordered steps laid out in space
    "diagram",              # abstract/relational layout
    "data",                 # data visualisation
    "system_action",        # a tool the assistant is about to run
    "transition",           # pure avatar/object transition
)

# ── Object catalogue ──────────────────────────────────────────────────────────
# kind: the builder id used by the renderer (avatar3d.js).
# semantic: the default semantic colour (overridable per intent).
# scale:   world-space sizing hint (multiplicative head-unit).
# interior: the object has interior detail shown for "show the inside of X".
OBJECTS: dict[str, dict] = {
    "apple":       {"kind": "apple",       "semantic": "#ff3045",
                    "scale": 0.9, "interior": True},
    "sphere":      {"kind": "sphere",      "semantic": "#00d4ff", "scale": 0.8},
    "cube":        {"kind": "cube",        "semantic": "#00d4ff", "scale": 0.8},
    "torus":       {"kind": "torus",       "semantic": "#00d4ff", "scale": 0.8},
    "cone":        {"kind": "cone",        "semantic": "#00d4ff", "scale": 0.8},
    "cylinder":    {"kind": "cylinder",    "semantic": "#00d4ff", "scale": 0.8},
    "capsule":     {"kind": "capsule",     "semantic": "#00d4ff", "scale": 0.8},
    "icosa":       {"kind": "icosa",       "semantic": "#00d4ff", "scale": 0.8},
    "planet":      {"kind": "planet",      "semantic": "#3b72ff",
                    "scale": 1.0, "interior": True},
    "sun":         {"kind": "sun",         "semantic": "#ffb84d", "scale": 1.2},
    "moon":        {"kind": "moon",        "semantic": "#9eb2c8", "scale": 0.5},
    "sunglasses":  {"kind": "sunglasses",  "semantic": "#00111e", "scale": 0.5},
    "watch":       {"kind": "watch",       "semantic": "#ffc94d", "scale": 0.42},
    "ring":        {"kind": "ring",        "semantic": "#ffc94d", "scale": 0.3},
    "necklace":    {"kind": "necklace",    "semantic": "#ffc94d", "scale": 0.5},
    "hat":         {"kind": "hat",         "semantic": "#3b72ff", "scale": 0.7},
    "tree":        {"kind": "tree",        "semantic": "#2ec46a", "scale": 1.4},
    "ground":      {"kind": "ground",      "semantic": "#0a2036", "scale": 6.0},
}

# ── Environment catalogue (for story / scene modes) ──────────────────────────
ENVIRONMENTS: tuple[str, ...] = (
    "minimal", "space", "forest", "desert", "city", "ocean",
)

# ── Materials ─────────────────────────────────────────────────────────────────
MATERIALS: tuple[str, ...] = (
    "holographic", "glass", "metal", "matte", "emissive", "particle", "transparent",
)

# ── Camera modes ──────────────────────────────────────────────────────────────
CAMERA_MODES: tuple[str, ...] = (
    "default", "portrait", "focus", "orbit", "zoom", "closeup",
    "wide", "top_down", "side", "inspection", "cinematic", "follow",
)

# ── Animations the renderer understands ───────────────────────────────────────
ANIMATIONS: tuple[str, ...] = (
    "rotate", "assemble", "dissolve", "pulse", "orbit", "bounce",
    "highlight", "scan", "float", "idle",
)

# ── Semantic colour tokens.  A raw #rrggbb hex is also accepted by the
#    validator — this map just gives Gemini convenient named tokens. ─────────
SEMANTIC_COLORS: dict[str, str] = {
    "opero":        "#00d4ff",   # the OPERO identity blue/cyan
    "cyan":         "#00d4ff",
    "blue":         "#3b72ff",
    "red":          "#ff3045",
    "apple_red":    "#ff3045",
    "green":        "#00ff88",
    "plant_green":  "#2ec46a",
    "fire_orange":  "#ff6b00",
    "orange":       "#ff8a2a",
    "gold":         "#ffc94d",
    "ocean":        "#1e90ff",
    "earth":        "#3b72ff",
    "violet":       "#8a5cff",
    "warning":      "#ff3355",
    "white":        "#d8f8ff",
    "grey":         "#7f8ea0",
    "black":        "#00111e",
}

# ── Body anchors (accessory attachment points) ────────────────────────────────
# The current head mesh derives eye/ear/neck/face/head.  Shoulder/wrist/… belong
# to the phase-5 body rig; they are already part of the vocabulary so intent
# schemas stay stable when that rig lands.
ANCHORS: tuple[str, ...] = (
    "head", "face", "left_eye", "right_eye", "left_ear", "right_ear",
    "neck", "chest", "left_shoulder", "right_shoulder",
    "left_hand", "right_hand", "left_wrist", "right_wrist",
    "left_index", "right_index", "waist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_foot", "right_foot",
)

# Accessory ids map onto the anchor they attach to by default.
ACCESSORY_ANCHOR: dict[str, str] = {
    "sunglasses": "face",
    "watch":      "left_wrist",
    "ring":       "left_index",
    "necklace":   "neck",
    "hat":        "head",
}

# Highlights that are generic semantics, not object-specific hacks.
INTERIOR_TOKENS: tuple[str, ...] = (
    "core", "inside", "cutaway", "internal", "seeds", "cross-section",
)

# Hard bounds applied by the validator (protects the renderer and the GPU).
LIMITS: dict[str, float] = {
    "duration_min": 1.0,
    "duration_max": 120.0,
    "story_scenes_max": 8,
    "story_objects_max": 6,
    "highlight_max": 8,
    "subject_len_max": 48,
    "particle_scale_max": 2.0,
}