"""Tests for explicit visual request routing (visual command routing)."""

import pytest

from core.visual import (
    SEARCH_GUARD_TOOLS,
    IntentAction,
    IntentMode,
    UnknownConceptError,
    VisualRouter,
    last_user_utterance,
    route_search_request,
    route_visual_request,
)


def test_show_me_an_apple_routes_to_visual_intent() -> None:
    routed = route_visual_request("show me an apple")
    assert routed is not None
    intent = routed.intent
    assert intent.mode is IntentMode.OBJECT
    assert intent.action is IntentAction.SHOW
    assert intent.concept_id == "apple"
    assert intent.entity_id is None
    assert routed.entity_id == "apple_01"
    assert routed.asset_id == "apple_default"
    assert routed.asset_status.value == "pending"


@pytest.mark.parametrize(
    "utterance",
    ["show me an apple", "visualize an apple", "show me a 3D apple", "show the apple"],
)
def test_explicit_visual_phrases_route(utterance: str) -> None:
    routed = route_visual_request(utterance)
    assert routed is not None
    assert routed.intent.action is IntentAction.SHOW
    assert routed.intent.concept_id == "apple"


def test_routed_entity_is_reused_not_duplicated() -> None:
    router = VisualRouter()
    first = route_visual_request("show me an apple", router=router)
    second = route_visual_request("show the apple", router=router)
    assert first is not None and second is not None
    assert first.entity_id == second.entity_id == "apple_01"


def test_explicit_visual_request_does_not_become_search() -> None:
    searches: list[dict] = []

    def fake_search(args: dict) -> str:
        searches.append(args)
        return "web results"

    def dispatch(name: str, args: dict, utterance: str) -> str:
        # Mirrors the guard in main.py OperaLive._execute_tool.
        routed = route_search_request(name, args, utterance)
        if routed is not None:
            return "visual"
        fake_search(args)
        return "search"

    assert dispatch("web_search", {"query": "show me an apple"}, "show me an apple") == "visual"
    assert searches == []
    # Gemini distilled the query — the raw utterance still catches it.
    assert dispatch("browser_control", {"query": "apple images"}, "show me an apple") == "visual"
    assert searches == []
    # Ordinary search requests still search.
    assert dispatch("web_search", {"query": "weather in tokyo"}, "weather in tokyo") == "search"
    assert searches == [{"query": "weather in tokyo"}]
    # Non-search tools are untouched by the guard.
    assert "web_search" in SEARCH_GUARD_TOOLS
    assert route_search_request("save_memory", {"query": "show me an apple"}, "show me an apple") is None
    # A plain "show" of a non-concept is not a 3D request.
    assert route_visual_request("show me the weather") is None


def test_unknown_visual_concept_rejected_cleanly() -> None:
    with pytest.raises(UnknownConceptError, match="dragon"):
        route_visual_request("visualize a dragon")
    with pytest.raises(UnknownConceptError, match="dragon"):
        route_visual_request("show me a 3D dragon")
    # The dispatcher guard surfaces the rejection instead of searching.
    with pytest.raises(UnknownConceptError):
        route_search_request("web_search", {"query": "show me a 3d dragon"}, "")


def test_last_user_utterance_extracted_from_session_log() -> None:
    log = ["User: show me an apple", "Opera: sure"]
    assert last_user_utterance(log) == "show me an apple"
    assert last_user_utterance(["Opera: hi"]) == ""
    assert last_user_utterance([]) == ""
