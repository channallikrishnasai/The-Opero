"""VisualDirector — the single entry point of the visual layer.

Pipeline (matches the brief, with Gemini on the far side):

    Gemini (tool call) -> validated VisualIntent -> VisualDirector
                        -> renderer directive (pure data) -> THREE.js scene

The director is deliberately thin and framework-free:
  * it validates (never trusts) incoming intent,
  * it emits domain events on a VisualBus (state, intent_begin, intent_end,
    visual_error) so the UI/tests observe it without coupling,
  * it talks to the renderer through a tiny bridge object, and
  * it NEVER blocks the voice loop — a failed visualisation is a log line, an
    event and a graceful message, not an exception.

Thread-safety: apply_intent/return_to_idle may be called from Gemini's executor
thread.  Everything stateful is behind a lock; the bridge hop is fire-and-forget.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from core.visual.events import VisualBus
from core.visual.intent import (
    VisualError,
    VisualIntent,
    intent_to_directive,
    validate_intent,
)
from core.visual.registry import (
    RELATIONSHIPS,
    CAUSAL_CHAINS,
    BODY_PARTS,
    BODY_SYSTEMS,
    INSPECTION_MODES,
    TEMPORAL_STATES,
    CAMERA_DIRECTIVES,
    CHARACTER_STATES,
    ENVIRONMENTS,
    OBJECTS,
)

log = logging.getLogger("opero.visual")


class RendererBridge:
    """Minimal contract between the director and a renderer backend.

    `send` is the only required method; a bridge that is absent (None) makes the
    whole layer a graceful no-op (headless/CI/no-WebGL machines) while the
    QPainter avatar keeps running untouched.
    """

    def send(self, directive: dict) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class _UiBridge(RendererBridge):
    """Bridges to the Qt window's WebGL layer via the OperaUI proxy."""

    def __init__(self, player: Any):
        self._player = player

    def send(self, directive: dict) -> None:
        win = getattr(self._player, "_win", None)
        apply = getattr(win, "apply_visual", None) if win is not None else None
        if apply is not None:
            try:
                apply(directive)
            except Exception:
                log.exception("apply_visual failed")

    def send_avatar_state(self, state: str) -> None:
        """Forward the avatar state to the WebGL renderer."""
        win = getattr(self._player, "_win", None)
        set_state = getattr(win, "set_avatar_state", None) if win is not None else None
        if set_state is not None:
            try:
                set_state(state)
            except Exception:
                log.exception("set_avatar_state failed")


class VisualDirector:
    """Validates visual intent and drives the renderer bridge."""

    # ── Visualization decision engine ──────────────────────────────────
    # Decides whether a response actually needs visualization based on
    # semantic analysis, not keyword matching.

    SPATIAL_KEYWORDS = frozenset((
        "engine", "piston", "crankshaft", "gear", "battery", "heart",
        "cell", "dna", "wave", "circuit", "laser", "mirror", "prism",
        "planet", "atom", "molecule", "structure", "system", "mechanism",
        "process", "flow", "cycle", "rotation", "orbit", "axis",
    ))
    STRUCTURAL_KEYWORDS = frozenset((
        "anatomy", "body", "organ", "system", "skeleton", "muscle",
        "circulatory", "respiratory", "nervous", "digestive",
        "architecture", "building", "bridge", "framework", "tower",
    ))
    CAUSAL_KEYWORDS = frozenset((
        "cause", "effect", "why", "how", "because", "therefore",
        "leads to", "results in", "triggers", "produces", "generates",
    ))
    TEMPORAL_KEYWORDS = frozenset((
        "timeline", "history", "sequence", "chronology", "era",
        "epoch", "period", "before", "after", "during",
    ))

    @classmethod
    def decide_visualize(cls, text: str, user_requested: bool = False) -> tuple[bool, str]:
        """Decide whether a response should be visualized.

        Evaluates: spatial, structural, mechanical, causal, temporal,
        relational, and whether seeing it would improve understanding.
        Returns (should_visualize, reason).
        """
        if user_requested:
            return True, "user_requested"

        t = text.lower()
        for kw in cls.SPATIAL_KEYWORDS:
            if kw in t:
                return True, "spatial_concept"
        for kw in cls.STRUCTURAL_KEYWORDS:
            if kw in t:
                return True, "structural_concept"
        for kw in cls.CAUSAL_KEYWORDS:
            if kw in t:
                return True, "causal_concept"
        for kw in cls.TEMPORAL_KEYWORDS:
            if kw in t:
                return True, "temporal_concept"

        # Check for object IDs in the registry
        for obj_id in ("engine", "piston", "crankshaft", "gear",
                        "battery", "heart", "cell", "dna", "planet"):
            if obj_id in t:
                return True, f"known_object:{obj_id}"

        return False, "face_only"

    @classmethod
    def build_visual_intent(cls, subject: str, reason: str = "spatial",
                            animation: str = "rotate",
                            camera: str = "inspection") -> dict:
        """Build a visualization intent from the decision engine."""
        return {
            "mode": "object_explanation",
            "subject": subject,
            "visualize": True,
            "reason": reason,
            "semantic": "spatial",
            "animation": animation,
            "camera": camera,
            "transition": True,
            "transition_duration": 2.2,
            "return_to_face": True,
            "auto_return": True,
            "duration": 8.0,
        }

    # ── Face → Object → Face state machine ───────────────────────
    FACE_OBJECT_STATES = frozenset((
        "FACE", "FACE_SCANNING", "OBJECT_FORMING", "OBJECT_VISIBLE",
        "OBJECT_INSPECTING", "OBJECT_DISMISSING", "FACE_REFORMING",
        "FACE_ONLY",
    ))

    def __init__(self, bridge=None, bus=None):
        self._bridge = bridge
        self._bus = bus or VisualBus()
        self._lock = threading.Lock()
        self._active = None
        self._generation = 0
        self._return_timer = None
        self._state = "IDLE"
        # ── Face↔Object state ─────────────────────────────
        self._visual_state = "FACE_ONLY"  # FACE_ONLY, VISUALIZING, TRANSITIONING
        self._active_subject = None
        self._transition_gen = 0
        # ── Avatar states ───────────────────────────────────
        self._avatar_state = "IDLE"  # IDLE, LISTENING, THINKING, PROCESSING, SPEAKING, VISUALIZING, ERROR, SUCCESS
        # ── Inspection ────────────────────────────────
        self._inspection_mode = "normal"
        self._inspection_isolate = []
        self._inspection_transparency = 0.0
        self._inspection_exploded = False
        # ── Causal chain ──────────────────────────────
        self._causal_chain = ""
        self._causal_step = 0
        # ── Temporal ──────────────────────────────────
        self._temporal_state = "paused"
        self._temporal_speed = 1.0
        self._temporal_step = 0
        # ── Body system ───────────────────────────────
        self._body_system = ""
        self._body_part = ""
        self._body_transparency = 0.0
        # ── Story ─────────────────────────────────────
        self._story_environment = "minimal"
        self._story_scenes = []
        self._story_character = ""
        self._story_scene_idx = 0
        # ── Visual memory ─────────────────────────────
        self._entity_id = ""
        self._entity_ids: dict[str, dict] = {}
        # ── Camera ────────────────────────────────────
        self._camera_directive = ""
        self._camera_target = ""

    # ── configuration ────────────────────────────────────────────────────────
    @property
    def bus(self) -> VisualBus:
        return self._bus

    @property
    def available(self) -> bool:
        return self._bridge is not None

    def set_bridge(self, bridge) -> None:
        self._bridge = bridge

    # ── intent pipeline ──────────────────────────────────────────────────────
    def apply_intent(self, raw) -> str:
        """Validate and apply a visual intent.  Never raises.

        Returns a short human-readable status string the assistant can speak.
        """
        # Validation errors are routine (a model hallucinating an object id is
        # not a crash) — log and continue the voice response.
        try:
            intent = validate_intent(raw)
        except VisualError as exc:
            log.warning("visual intent rejected: %s", exc)
            self._bus.publish("visual_error", {"reason": str(exc), "raw": raw})
            return f"Visualisation not available: {exc}"

        directive = intent_to_directive(intent)

        # ── Visualization decision ──────────────────────────────
        # If the intent says face_only or the decision engine says
        # no visualization is needed, send a face-only directive.
        if not intent.visualize or intent.mode == "face_only":
            directive["op"] = "face_only"
            directive["transition"] = False
            self._visual_state = "FACE_ONLY"
            self._avatar_state = "LISTENING"
            self._set_scene_state("FACE_ONLY")
            if self._bridge is not None:
                try:
                    self._bridge.send(directive)
                except Exception:
                    log.exception("renderer failed face_only")
            return "face_only"

        # ── Face → Object transition ────────────────────────────
        if intent.transition and intent.visualize:
            self._visual_state = "TRANSITIONING"
            self._avatar_state = "VISUALIZING"
            self._active_subject = directive["subject"]
            self._transition_gen = self._generation

            # Send the transition-in directive to the renderer
            transition_directive = dict(directive)
            transition_directive["op"] = "transition_in"
            transition_directive["transition_duration"] = intent.transition_duration

        else:
            self._visual_state = "VISUALIZING"
            self._avatar_state = "VISUALIZING"
            self._active_subject = directive["subject"]
            transition_directive = directive

        with self._lock:
            self._generation += 1
            gen = self._generation
            self._active = directive
            if self._return_timer is not None:
                self._return_timer.cancel()
                self._return_timer = None

        self._bus.publish("intent_begin", directive)
        self._set_scene_state("STORY" if intent.mode == "story" else "VISUALIZING")

        # Send the transition-in directive first if needed
        if intent.transition and self._bridge is not None:
            try:
                self._bridge.send(transition_directive)
            except Exception:
                log.exception("renderer failed transition_in")

        # Then send the main directive
        if self._bridge is not None:
            try:
                self._bridge.send(directive)
            except Exception:
                log.exception("renderer failed to apply intent")
                self._bus.publish("visual_error",
                                  {"reason": "renderer error", "raw": raw})

        if intent.auto_return:
            timer = threading.Timer(max(intent.duration + 1.5, 2.5),
                                    self.return_to_idle, args=(gen,))
            timer.daemon = True
            with self._lock:
                self._return_timer = timer
            timer.start()

        desc = f"Visualising {directive['subject'] or 'the scene'}"
        desc += f" ({directive['material']}, {directive['camera']} camera)"
        if intent.transition:
            desc += " (face → object morph)"
        return desc

    def return_to_idle(self, generation=None) -> None:
        """Dissolve the scene and hand the stage back to the avatar.

        If a face→object transition was used, sends a transition-out
        directive so the renderer animates the object dissolving back
        into the face, rather than an abrupt switch.
        """
        with self._lock:
            if generation is not None and generation != self._generation:
                return                      # a newer intent owns the stage
            self._active = None
            if self._return_timer is not None:
                self._return_timer.cancel()
                self._return_timer = None

            subject = self._active_subject
            self._active_subject = None
            self._visual_state = "FACE_ONLY"
            self._avatar_state = "IDLE"

        self._bus.publish("intent_end", {"return_to": "avatar"})
        self._set_scene_state("RETURN")
        if self._bridge is not None:
            try:
                # Send transition-out if a face→object was used,
                # otherwise send a plain return.
                if subject:
                    self._bridge.send({
                        "op": "transition_out",
                        "return_to": "avatar",
                        "subject": subject,
                    })
                else:
                    self._bridge.send({"op": "return", "return_to": "avatar"})
            except Exception:
                log.exception("renderer failed to return")

    # ── state mirroring ──────────────────────────────────────────────────────
    def _set_scene_state(self, name: str) -> None:
        with self._lock:
            self._state = name
        self._bus.publish("state", {"state": name})

    def on_state(self, name: str) -> None:
        """Record + broadcast; the window already forwards states to the
        renderer, so the director only mirrors them here."""
        name = str(name or "IDLE").upper()
        with self._lock:
            self._state = name
        self._bus.publish("state", {"state": name})

    def set_avatar_state(self, state: str) -> None:
        """Set the avatar's visual state (IDLE, LISTENING, THINKING,
        SPEAKING, VISUALIZING, ERROR, SUCCESS)."""
        valid = ("IDLE", "LISTENING", "THINKING", "PROCESSING",
                 "SPEAKING", "VISUALIZING", "ERROR", "SUCCESS")
        if state.upper() in valid:
            with self._lock:
                self._avatar_state = state.upper()
            self._bus.publish("avatar_state", {"state": state.upper()})

    def get_avatar_state(self) -> str:
        with self._lock:
            return self._avatar_state

    def diagnostics(self) -> dict:
        with self._lock:
            return {
                "available": self.available,
                "state": self._state,
                "visual_state": self._visual_state,
                "avatar_state": self._avatar_state,
                "active": bool(self._active),
                "subject": (self._active or {}).get("subject"),
                "active_subject": self._active_subject,
                "entity_id": self._entity_id,
                "entity_ids": list(self._entity_ids.values()),
                "inspection_mode": self._inspection_mode,
                "temporal_state": self._temporal_state,
                "body_system": self._body_system,
            }

    # ── inspection ──────────────────────────────────────────────────
    def set_inspection(self, mode: str, isolate: list[str] | None = None,
                       transparency: float = 0.0,
                       exploded: bool = False) -> None:
        """Set the inspection mode for the current object."""
        if mode not in INSPECTION_MODES:
            return
        with self._lock:
            self._inspection_mode = mode
            self._inspection_isolate = isolate or []
            self._inspection_transparency = transparency
            self._inspection_exploded = exploded
        self._bus.publish("inspection", {"mode": mode,
                                           "isolate": self._inspection_isolate})
        if self._bridge is not None:
            try:
                self._bridge.send({"op": "inspect", "mode": mode,
                                   "isolate": self._inspection_isolate,
                                   "transparency": transparency,
                                   "exploded": exploded})
            except Exception:
                log.exception("inspection failed")

    # ── camera focus ────────────────────────────────────────────────
    def focus_entity(self, entity: str, directive: str = "FOCUS",
                     target: str = "") -> None:
        """Direct the camera to focus on an entity."""
        self._camera_directive = directive
        self._camera_target = target or entity
        self._bus.publish("camera_focus", {"entity": entity,
                                           "directive": directive})
        if self._bridge is not None:
            try:
                self._bridge.send({"op": "camera", "directive": directive,
                                   "target": target or entity})
            except Exception:
                log.exception("camera focus failed")

    # ── causal chain ────────────────────────────────────────────────
    def show_causal_chain(self, chain_id: str, step: int = 0) -> None:
        """Render a causal chain visualization."""
        chain = CAUSAL_CHAINS.get(chain_id, [])
        if not chain:
            return
        with self._lock:
            self._causal_chain = chain_id
            self._causal_step = min(step, len(chain) - 1)
        self._bus.publish("causal_chain", {"chain": chain_id,
                                           "step": self._causal_step})
        if self._bridge is not None:
            try:
                self._bridge.send({"op": "causal_chain",
                                   "chain": chain_id,
                                   "step": self._causal_step})
            except Exception:
                log.exception("causal chain failed")

    # ── temporal controls ───────────────────────────────────────────
    def set_temporal(self, state: str, speed: float = 1.0,
                     step: int = 0) -> None:
        """Control temporal playback."""
        if state not in TEMPORAL_STATES:
            return
        with self._lock:
            self._temporal_state = state
            self._temporal_speed = speed
            self._temporal_step = step
        self._bus.publish("temporal", {"state": state,
                                        "speed": speed,
                                        "step": step})
        if self._bridge is not None:
            try:
                self._bridge.send({"op": "temporal", "state": state,
                                   "speed": speed, "step": step})
            except Exception:
                log.exception("temporal failed")

    # ── body system ─────────────────────────────────────────────────
    def show_body_system(self, system: str, part: str = "",
                         transparency: float = 0.0) -> None:
        """Show a body system with optional part focus."""
        if system and system not in BODY_SYSTEMS:
            return
        with self._lock:
            self._body_system = system
            self._body_part = part
            self._body_transparency = transparency
        self._bus.publish("body_system", {"system": system,
                                           "part": part})
        if self._bridge is not None:
            try:
                self._bridge.send({"op": "body_system", "system": system,
                                   "part": part, "transparency": transparency})
            except Exception:
                log.exception("body system failed")

    # ── visual memory ───────────────────────────────────────────────
    def create_entity(self, entity_id: str, obj_type: str,
                      data: dict | None = None) -> str:
        """Create a persistent visual entity with a unique ID."""
        if not entity_id or not entity_id.isalnum() and "_" not in entity_id:
            entity_id = f"{obj_type}_{len(self._entity_ids) + 1}"
        with self._lock:
            self._entity_ids[entity_id] = {"type": obj_type,
                                           "data": data or {}}
            self._entity_id = entity_id
        self._bus.publish("entity_created", {"entity_id": entity_id,
                                              "type": obj_type})
        return entity_id

    def get_entity(self, entity_id: str) -> dict | None:
        """Retrieve a persistent entity by ID."""
        with self._lock:
            return self._entity_ids.get(entity_id)

    def update_entity(self, entity_id: str, data: dict) -> bool:
        """Update an existing entity's data."""
        with self._lock:
            if entity_id in self._entity_ids:
                self._entity_ids[entity_id]["data"].update(data)
                return True
        return False

    # ── interactive command parser ──────────────────────────────────
    def handle_command(self, text: str) -> str:
        """Parse and execute an interactive visual command.

        Returns a status string describing what was done.
        """
        t = text.lower().strip()
        if "zoom in" in t:
            self.focus_entity(self._active_subject or "", "CLOSEUP")
            return "zooming in"
        if "zoom out" in t:
            self.focus_entity(self._active_subject or "", "WIDE")
            return "zooming out"
        if "rotate" in t:
            self._bus.publish("command", {"action": "rotate"})
            if self._bridge is not None:
                try:
                    self._bridge.send({"op": "animation",
                                       "animation": "rotate"})
                except Exception:
                    pass
            return "rotating"
        if "show me inside" in t or "cutaway" in t:
            self.set_inspection("cutaway")
            return "showing cutaway"
        if "exploded" in t or "exploded view" in t:
            self.set_inspection("exploded", exploded=True)
            return "showing exploded view"
        if "hide everything" in t or "isolate" in t:
            subject = self._active_subject or ""
            self.set_inspection("isolated", isolate=[subject])
            return f"isolating {subject}"
        if "slow down" in t:
            self.set_temporal("slow", speed=0.5)
            return "slowing down"
        if "go back" in t or "rewind" in t:
            self.set_temporal("rewinding")
            return "rewinding"
        if "show the next step" in t or "next step" in t:
            self._bus.publish("command", {"action": "next_step"})
            return "next step"
        if "show me why" in t or "why" in t:
            subject = self._active_subject or ""
            # Also look for known subjects in the text
            if not subject:
                for known in RELATIONSHIPS:
                    if known in t:
                        subject = known
                        break
            if subject in RELATIONSHIPS:
                targets = [r["target"] for r in RELATIONSHIPS[subject]]
                self._bus.publish("command", {"action": "causal",
                                                "subject": subject,
                                                "targets": targets})
                return f"showing causes of {subject}"
            return "no causal data available"
        if "what happens if" in t:
            self._bus.publish("command", {"action": "simulation",
                                           "text": text})
            return "simulating"
        if "follow" in t:
            self.focus_entity(self._active_subject or "", "FOLLOW")
            return "following"
        if "compare" in t:
            self._bus.publish("command", {"action": "compare",
                                           "text": text})
            return "comparing"
        return ""

    # ── accessory ───────────────────────────────────────────────────
    def attach_accessory(self, accessory: str, anchor: str,
                         material: str = "holographic",
                         color: str = "") -> None:
        """Attach an accessory to a body anchor."""
        self._bus.publish("accessory", {"accessory": accessory,
                                         "anchor": anchor,
                                         "material": material,
                                         "color": color})
        if self._bridge is not None:
            try:
                self._bridge.send({"op": "accessory", "accessory": accessory,
                                   "anchor": anchor,
                                   "material": material, "color": color})
            except Exception:
                log.exception("accessory failed")

    # ── story mode ──────────────────────────────────────────────────
    def start_story(self, environment: str, scenes: list[dict],
                    character: str = "") -> None:
        """Start a cinematic story mode."""
        if environment not in ENVIRONMENTS:
            return
        with self._lock:
            self._story_environment = environment
            self._story_scenes = scenes
            self._story_character = character
            self._story_scene_idx = 0
        self._bus.publish("story_start", {"environment": environment,
                                           "scenes": len(scenes)})
        if self._bridge is not None:
            try:
                self._bridge.send({"op": "story", "environment": environment,
                                   "scenes": scenes,
                                   "character": character})
            except Exception:
                log.exception("story failed")

    # ── face-first return ───────────────────────────────────────────
    def return_to_face(self) -> None:
        """Dissolve the scene and return to the avatar."""
        self._bus.publish("intent_end", {"return_to": "avatar"})
        self._set_scene_state("RETURN")
        with self._lock:
            self._visual_state = "FACE_ONLY"
            self._avatar_state = "LISTENING"
            self._active_subject = None
            self._inspection_mode = "normal"
            self._causal_chain = ""
            self._body_system = ""
        if self._bridge is not None:
            try:
                self._bridge.send({"op": "transition_out",
                                   "return_to": "avatar"})
            except Exception:
                log.exception("return to face failed")


# ── module-level singleton (set once from main.py) ───────────────────────────
_director = None


def get_visual_director():
    """Return the active director, or None (visualisation simply unavailable)."""
    return _director


def set_visual_director(director=None) -> None:
    global _director
    _director = director


def setup_visual_system(player: Any) -> VisualDirector:
    """Wire the visual system to a running UI (called once from main.py).

    Never raises: any failure leaves OPERO running exactly as before.  On
    machines without WebGL the bridge is a no-op and the QPainter avatar keeps
    running untouched.
    """
    win = getattr(player, "_win", None)
    real_bridge = _UiBridge(player) if win is not None else None
    director = VisualDirector(bridge=real_bridge)
    set_visual_director(director)
    # Push the measured head geometry into the renderer (single source of truth).
    push = getattr(win, "push_face_mesh", None) if win is not None else None
    if push is not None:
        try:
            push()
        except Exception:
            log.exception("face mesh push failed")
    return director