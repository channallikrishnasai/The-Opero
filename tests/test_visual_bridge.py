"""Bridge contract tests: VisualIntent → entity resolution → asset selection →
renderer command. The actual renderer (Qt widget / Three.js) is mocked as a
recording transport — no GPU, browser, or window system involved.
"""

import base64

import pytest

from core.visual import (
    AssetRecord,
    AssetRegistry,
    IntentAction,
    VisualBridge,
    VisualIntent,
    VisualWorldModel,
    register_bundled_assets,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.commands: list[dict] = []

    def __call__(self, command: dict) -> None:
        self.commands.append(command)


@pytest.fixture()
def transport() -> RecordingTransport:
    return RecordingTransport()


@pytest.fixture()
def bridge(transport: RecordingTransport) -> VisualBridge:
    registry = AssetRegistry()
    register_bundled_assets(registry)
    return VisualBridge(world=VisualWorldModel(), registry=registry, dispatch=transport)


def _show() -> VisualIntent:
    return VisualIntent(action=IntentAction.SHOW, concept_id="apple")


def test_show_intent_reaches_renderer_with_real_asset(bridge: VisualBridge, transport: RecordingTransport) -> None:
    result = bridge.execute(_show())

    assert result == {"success": True, "action": "show", "entity_id": "apple_01", "asset_id": "apple_default"}
    assert len(transport.commands) == 1
    command = transport.commands[0]
    assert command["action"] == "show"
    assert command["entity"] == {"id": "apple_01", "concept": "apple"}
    assert command["asset"] == {
        "asset_id": "apple_default",
        "path": "data/visual_world/assets/apple.glb",
        "format": "glb",
    }
    assert command["transform"] == {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
    assert base64.b64decode(command["data_base64"])[:4] == b"glTF"


def test_show_reuses_live_entity(bridge: VisualBridge, transport: RecordingTransport) -> None:
    first = bridge.execute(_show())
    second = bridge.execute(_show())

    assert first["entity_id"] == second["entity_id"] == "apple_01"
    assert len(bridge.world.to_dict()["entities"]) == 1
    assert [command["entity"]["id"] for command in transport.commands] == ["apple_01", "apple_01"]


def test_unknown_concept_is_structured(bridge: VisualBridge, transport: RecordingTransport) -> None:
    result = bridge.execute(VisualIntent(action="show", concept_id="banana"))

    assert result["success"] is False
    assert result["error"] == "unknown_concept"
    assert bridge.world.to_dict()["entities"] == []
    assert transport.commands == []


def test_missing_asset_is_structured(transport: RecordingTransport) -> None:
    bridge = VisualBridge(world=VisualWorldModel(), registry=AssetRegistry(), dispatch=transport)

    result = bridge.execute(_show())

    assert result["success"] is False
    assert result["error"] == "missing_asset"
    assert "pending" in result["message"]
    assert transport.commands == []


def test_invalid_asset_is_structured(transport: RecordingTransport) -> None:
    registry = AssetRegistry()
    registry.register_asset(
        AssetRecord(
            asset_id="apple_default",
            concept_id="apple",
            path="site/web_background/index.html",
            format="gltf",
            status="available",
        )
    )
    bridge = VisualBridge(world=VisualWorldModel(), registry=registry, dispatch=transport)

    result = bridge.execute(_show())

    assert result["success"] is False
    assert result["error"] == "invalid_asset"
    assert transport.commands == []


def test_corrupt_glb_reports_asset_load_failed(transport: RecordingTransport) -> None:
    registry = AssetRegistry()
    registry.register_asset(
        AssetRecord(
            asset_id="apple_default",
            concept_id="apple",
            path="site/web_background/index.html",
            format="glb",
            status="available",
        )
    )
    bridge = VisualBridge(world=VisualWorldModel(), registry=registry, dispatch=transport)

    result = bridge.execute(_show())

    assert result["success"] is False
    assert result["error"] == "asset_load_failed"
    assert set(result) == {"success", "error", "message"}
    assert "Traceback" not in result["message"]
    assert transport.commands == []


def test_hide_hides_entity(bridge: VisualBridge, transport: RecordingTransport) -> None:
    bridge.execute(_show())

    result = bridge.execute(VisualIntent(action="hide", entity_id="apple_01"))

    assert result == {"success": True, "action": "hide", "entity_id": "apple_01"}
    assert transport.commands[-1] == {"action": "hide", "entity": {"id": "apple_01", "concept": "apple"}}
    assert bridge.world.get_entity("apple_01").visible is False
    bridge.execute(_show())
    assert bridge.world.get_entity("apple_01").visible is True


def test_rotate_dispatches_speed(bridge: VisualBridge, transport: RecordingTransport) -> None:
    bridge.execute(_show())

    result = bridge.execute(VisualIntent(action="rotate", entity_id="apple_01", parameters={"speed": 2.0}))

    assert result["success"] is True
    command = transport.commands[-1]
    assert command["action"] == "rotate"
    assert command["entity"]["id"] == "apple_01"
    assert command["parameters"] == {"speed": 2.0}


def test_zoom_dispatches(bridge: VisualBridge, transport: RecordingTransport) -> None:
    bridge.execute(_show())

    result = bridge.execute(VisualIntent(action="zoom", concept_id="apple"))

    assert result["success"] is True
    assert transport.commands[-1] == {
        "action": "zoom",
        "entity": {"id": "apple_01", "concept": "apple"},
        "parameters": {},
    }


def test_focus_dispatches(bridge: VisualBridge, transport: RecordingTransport) -> None:
    bridge.execute(_show())

    result = bridge.execute(VisualIntent(action="focus", entity_id="apple_01"))

    assert result["success"] is True
    assert transport.commands[-1] == {"action": "focus", "entity": {"id": "apple_01", "concept": "apple"}}


def test_return_to_face_needs_no_entity(bridge: VisualBridge, transport: RecordingTransport) -> None:
    result = bridge.execute(VisualIntent(action="return_to_face"))

    assert result == {"success": True, "action": "return_to_face"}
    assert transport.commands == [{"action": "return_to_face"}]


def test_hide_unknown_entity_is_structured(bridge: VisualBridge, transport: RecordingTransport) -> None:
    result = bridge.execute(VisualIntent(action="hide", entity_id="apple_99"))

    assert result["success"] is False
    assert result["error"] == "unknown_entity"
    assert transport.commands == []


def test_dispatch_failure_is_structured(transport: RecordingTransport) -> None:
    def boom(command: dict) -> None:
        raise RuntimeError("window is gone")

    registry = AssetRegistry()
    register_bundled_assets(registry)
    bridge = VisualBridge(world=VisualWorldModel(), registry=registry, dispatch=boom)

    result = bridge.execute(_show())

    assert result["success"] is False
    assert result["error"] == "renderer_unavailable"
    assert "window is gone" in result["message"]
