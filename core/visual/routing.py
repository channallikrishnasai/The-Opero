"""Deterministic routing of explicit visual requests to the VisualIntent layer.

"show me an apple" must terminate at VisualIntent -> WorldModel -> AssetRegistry
and must never fall through to a web or image search. Matching is purely
lexical (no model call), so it is deterministic and testable. The renderer is
out of scope here: a routed intent stops at this layer.
"""

import re
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .assets import AssetRegistry, AssetStatus
from .concepts import UnknownConceptError, load_concepts
from .intent import EntityResolutionError, IntentAction, IntentMode, VisualIntent, resolve_entity_id
from .world_model import VisualWorldModel

SEARCH_GUARD_TOOLS = frozenset({"browser_control", "web_search", "youtube_video"})

_STRONG_VERBS = frozenset({"visualize", "visualise", "render"})

_HEAD_RE = re.compile(
    r"^(?:please\s+|could you\s+|can you\s+|would you\s+|let(?:'s)?\s+(?:see|view)\s+)*"
    r"(show|display|visuali[sz]e|render)"
    r"(?:\s+(?:me|us))?"
    r"(?:\s+(?:a|an|the|some|my|this|that))?"
    r"\s+(?P<rest>.+)$",
    re.IGNORECASE,
)
_LEADING_3D_RE = re.compile(r"^(?:3\s*-\s*d|3\s*d|three\s*dimensional)\s+", re.IGNORECASE)
_TRAILING_MODIFIER_RE = re.compile(
    r"(?:\s+(?:in|as)\s+(?:3\s*[-\s]?\s*d|three\s*dimensions?)|\s+on\s+(?:my\s+)?screen)\s*$",
    re.IGNORECASE,
)
_3D_ANYWHERE_RE = re.compile(r"\b3\s*[-\s]?\s*d\b", re.IGNORECASE)
_STRIP_CHARS = " \t.,!?;:'\""


def _match_request(text: str) -> tuple[str | None, bool]:
    """Return (requested noun, must_route).

    must_route is True when the phrasing is unambiguously 3D-visual (strong verb
    or an explicit "3d" marker), so an unknown noun must be rejected instead of
    falling through to a search. Plain "show ..." with an unknown noun stays a
    normal request (e.g. "show me the weather").
    """
    stripped = (text or "").strip()
    if not stripped:
        return None, False
    match = _HEAD_RE.match(stripped)
    if match is None:
        return None, False
    verb = match.group(1).lower()
    rest = match.group("rest")
    must_route = verb in _STRONG_VERBS or bool(_3D_ANYWHERE_RE.search(stripped))
    rest = _LEADING_3D_RE.sub("", rest)
    rest = _TRAILING_MODIFIER_RE.sub("", rest)
    noun = " ".join(rest.split()).strip(_STRIP_CHARS)
    if not noun:
        return None, False
    return noun, must_route


@dataclass(frozen=True)
class VisualRouteResult:
    """The terminal state of a routed visual request (no renderer attached)."""

    intent: VisualIntent
    entity_id: str
    asset_id: str
    asset_status: AssetStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "entity_id": self.entity_id,
            "asset_id": self.asset_id,
            "asset_status": self.asset_status.value,
        }


def last_user_utterance(session_log: Sequence[str]) -> str:
    """Most recent raw user utterance from a "User: ..." conversation log."""
    for entry in reversed(session_log):
        if isinstance(entry, str) and entry.startswith("User: "):
            return entry[6:].strip()
    return ""


class VisualRouter:
    """Terminates explicit visual requests at the WorldModel/AssetRegistry layer."""

    def __init__(self, world: VisualWorldModel | None = None, registry: AssetRegistry | None = None) -> None:
        self._concepts = load_concepts()
        self.world = world if world is not None else VisualWorldModel()
        self.registry = registry if registry is not None else AssetRegistry(concepts=self._concepts)

    def route(self, text: str) -> VisualRouteResult | None:
        noun, must_route = _match_request(text)
        if noun is None:
            return None
        if noun not in self._concepts:
            if not must_route:
                return None
            raise UnknownConceptError(
                f"visual concept {noun!r} is not in the vocabulary; known concepts: {sorted(self._concepts)}"
            )
        intent = VisualIntent(mode=IntentMode.OBJECT, action=IntentAction.SHOW, concept_id=noun)
        try:
            entity_id = resolve_entity_id(intent, self.world)
        except EntityResolutionError:
            entity_id = self.world.create_entity(noun).id
        asset = self.registry.find_for_concept(noun)
        return VisualRouteResult(intent=intent, entity_id=entity_id, asset_id=asset.asset_id, asset_status=asset.status)


_router: VisualRouter | None = None
_router_lock = threading.Lock()


def get_visual_router() -> VisualRouter:
    global _router
    if _router is None:
        with _router_lock:
            if _router is None:
                _router = VisualRouter()
    return _router


def route_visual_request(text: str, router: VisualRouter | None = None) -> VisualRouteResult | None:
    """Route one utterance; None means "not an explicit visual request"."""
    return (router if router is not None else get_visual_router()).route(text)


def route_search_request(name: str, args: dict[str, Any], utterance: str) -> VisualRouteResult | None:
    """Guard for search-capable tools: explicit visual requests never reach a search.

    Raises UnknownConceptError when the request is visually explicit but names
    no known concept, so the caller can reject it instead of searching.
    """
    if name not in SEARCH_GUARD_TOOLS:
        return None
    for candidate in (str(args.get("query") or ""), utterance):
        if not candidate.strip():
            continue
        result = route_visual_request(candidate)
        if result is not None:
            return result
    return None
