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
    "face_only",            # avatar only, no visualization
    "object_explanation",   # an object is shown, described, transformed
    "object_inspection",    # object with detailed inspection view
    "accessory",            # an object attaches to a body anchor
    "story",                # a sequence of scenes with an environment
    "process",              # ordered steps laid out in space
    "causal_chain",         # cause-and-effect chain visualization
    "body_system",          # anatomical/biological system
    "timeline",             # temporal sequence
    "diagram",              # abstract/relational layout
    "data",                 # data visualisation
    "simulation",           # interactive simulation
    "comparison",           # side-by-side comparison
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
    "engine":      {"kind": "icosa",       "semantic": "#ff6b00", "scale": 1.2, "interior": True},
    "piston":      {"kind": "cylinder",    "semantic": "#ff6b00", "scale": 0.8},
    "crankshaft":  {"kind": "cylinder",    "semantic": "#ff6b00", "scale": 1.0},
    "gear":        {"kind": "torus",       "semantic": "#ffc94d", "scale": 0.8},
    "battery":     {"kind": "cylinder",    "semantic": "#3b72ff", "scale": 0.6, "interior": True},
    "heart":       {"kind": "sphere",      "semantic": "#ff3045", "scale": 0.8, "interior": True},
    "cell":        {"kind": "sphere",      "semantic": "#2ec46a", "scale": 0.7, "interior": True},
    "dna":         {"kind": "icosa",       "semantic": "#3b72ff", "scale": 1.0},
    "wave":        {"kind": "plane",       "semantic": "#00e5ff", "scale": 1.5},
    "circuit":     {"kind": "cube",        "semantic": "#ffc94d", "scale": 0.8},
    "laser":       {"kind": "cylinder",    "semantic": "#ff3355", "scale": 0.5},
    "mirror":      {"kind": "cube",        "semantic": "#d8f8ff", "scale": 0.8},
    "prism":       {"kind": "icosa",       "semantic": "#ffb84d", "scale": 0.7},
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
    "overhead", "exploded", "cutaway",
)

# ── Animations the renderer understands ───────────────────────────────────────
ANIMATIONS: tuple[str, ...] = (
    "rotate", "assemble", "dissolve", "pulse", "orbit", "bounce",
    "highlight", "scan", "float", "idle", "appear", "disappear",
    "move", "scale", "morph", "explode", "implode", "flow",
    "walk", "transform", "blink", "breath",
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

# ── Body system parts ──────────────────────────────────────────────────
# Each body part maps to a 3D builder id and semantic colour.
BODY_PARTS: dict[str, dict] = {
    "head":        {"kind": "sphere",       "semantic": "#ffc94d", "scale": 0.9},
    "brain":       {"kind": "sphere",       "semantic": "#ffc94d", "scale": 0.5},
    "eyes":        {"kind": "sphere",       "semantic": "#00d4ff", "scale": 0.3},
    "mouth":       {"kind": "sphere",       "semantic": "#ff6b00", "scale": 0.3},
    "throat":      {"kind": "cylinder",     "semantic": "#ffc94d", "scale": 0.4},
    "heart":       {"kind": "sphere",       "semantic": "#ff3045", "scale": 0.6},
    "lungs":       {"kind": "sphere",       "semantic": "#ff8a8a", "scale": 0.7},
    "stomach":     {"kind": "sphere",       "semantic": "#ff8a2a", "scale": 0.6},
    "liver":       {"kind": "sphere",       "semantic": "#ff6b00", "scale": 0.5},
    "kidneys":     {"kind": "sphere",       "semantic": "#3b72ff", "scale": 0.4},
    "intestines":  {"kind": "torus",        "semantic": "#ffc94d", "scale": 0.6},
    "muscles":     {"kind": "capsule",      "semantic": "#ff6b00", "scale": 0.8},
    "bones":       {"kind": "icosa",        "semantic": "#d8f8ff", "scale": 0.9},
    "skin":        {"kind": "sphere",       "semantic": "#ffc94d", "scale": 1.0},
    "blood_vessels":{"kind": "cylinder",    "semantic": "#ff3355", "scale": 0.3},
    "nervous_system":{"kind": "icosa",     "semantic": "#00e5ff", "scale": 1.0},
    "chest":       {"kind": "cylinder",     "semantic": "#ff6b00", "scale": 0.8},
    "abdomen":     {"kind": "sphere",       "semantic": "#ff8a2a", "scale": 0.7},
    "pelvis":      {"kind": "sphere",       "semantic": "#3b72ff", "scale": 0.5},
    "brain_stem":  {"kind": "cylinder",     "semantic": "#00e5ff", "scale": 0.3},
}

# ── Semantic relationships ──────────────────────────────────────────────
# entity → [{"target": entity_id, "relation": "contains|uses|drives|connects|produces|flows_to"}, ...]
RELATIONSHIPS: dict[str, list[dict]] = {
    "engine": [
        {"target": "piston",    "relation": "contains"},
        {"target": "crankshaft", "relation": "contains"},
        {"target": "gear",      "relation": "contains"},
        {"target": "fuel",      "relation": "uses"},
        {"target": "air",       "relation": "uses"},
        {"target": "battery",   "relation": "uses"},
    ],
    "piston": [
        {"target": "crankshaft", "relation": "drives"},
        {"target": "engine",     "relation": "part_of"},
    ],
    "crankshaft": [
        {"target": "piston",     "relation": "driven_by"},
        {"target": "engine",     "relation": "part_of"},
    ],
    "gear": [
        {"target": "crankshaft", "relation": "connects"},
        {"target": "engine",     "relation": "part_of"},
    ],
    "battery": [
        {"target": "engine",     "relation": "powers"},
    ],
    "heart": [
        {"target": "blood_vessels", "relation": "drives"},
        {"target": "lungs",        "relation": "connects"},
        {"target": "brain",        "relation": "supplies"},
    ],
    "lungs": [
        {"target": "heart",       "relation": "connects"},
        {"target": "blood_vessels", "relation": "flows_to"},
    ],
    "brain": [
        {"target": "nervous_system", "relation": "is"},
        {"target": "heart",          "relation": "controls"},
    ],
    "apple": [
        {"target": "seeds",     "relation": "contains"},
        {"target": "skin",      "relation": "has"},
    ],
    "cell": [
        {"target": "dna",       "relation": "contains"},
        {"target": "nucleus",   "relation": "contains"},
    ],
}

# ── Causal chain templates ─────────────────────────────────────────────
# Each chain is an ordered list of steps with visual descriptions.
CAUSAL_CHAINS: dict[str, list[dict]] = {
    "engine_combustion": [
        {"step": 1, "label": "Fuel + Air",       "entity": "fuel",      "camera": "wide"},
        {"step": 2, "label": "Compression",      "entity": "piston",    "camera": "focus"},
        {"step": 3, "label": "Combustion",       "entity": "engine",    "camera": "closeup"},
        {"step": 4, "label": "Pressure",         "entity": "engine",    "camera": "focus"},
        {"step": 5, "label": "Piston Motion",    "entity": "piston",    "camera": "side"},
        {"step": 6, "label": "Crankshaft Rotation", "entity": "crankshaft", "camera": "focus"},
        {"step": 7, "label": "Rotation Output",  "entity": "gear",      "camera": "wide"},
    ],
    "circulation": [
        {"step": 1, "label": "Heart Pumps",      "entity": "heart",       "camera": "focus"},
        {"step": 2, "label": "Blood to Lungs",   "entity": "blood_vessels", "camera": "follow"},
        {"step": 3, "label": "Oxygenation",      "entity": "lungs",       "camera": "focus"},
        {"step": 4, "label": "Blood to Body",    "entity": "blood_vessels", "camera": "wide"},
        {"step": 5, "label": "Nutrient Delivery", "entity": "stomach",   "camera": "focus"},
    ],
}

# ── Inspection modes ────────────────────────────────────────────────────
INSPECTION_MODES: tuple[str, ...] = (
    "normal", "cutaway", "exploded", "transparent", "isolated",
    "cross_section", "wireframe", "xray",
)

# ── Temporal states ─────────────────────────────────────────────────────
TEMPORAL_STATES: tuple[str, ...] = (
    "playing", "paused", "slow", "fast", "stepped", "rewinding", "reset",
)

# ── Camera directives ───────────────────────────────────────────────────
CAMERA_DIRECTIVES: tuple[str, ...] = (
    "WIDE", "FOCUS", "CLOSEUP", "ORBIT", "FOLLOW",
    "TOP_DOWN", "CINEMATIC", "INSPECTION", "ZOOM_IN", "ZOOM_OUT",
    "PAN", "TRACK",
)

# ── Story character states ──────────────────────────────────────────────
CHARACTER_STATES: tuple[str, ...] = (
    "idle", "walking", "running", "entering", "exiting",
    "interacting", "speaking", "listening", "thinking",
)

# ── Body system groups ──────────────────────────────────────────────────
BODY_SYSTEMS: tuple[str, ...] = (
    "circulatory", "respiratory", "nervous", "digestive",
    "muscular", "skeletal", "endocrine", "lymphatic",
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
    "entity_id_len_max": 32,
    "causal_chain_max": 20,
    "body_parts_max": 50,
}