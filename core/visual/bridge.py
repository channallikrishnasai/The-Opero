"""Visual → renderer bridge: intents in, structured commands out.

The last hop of VisualIntent → WorldModel → AssetRegistry → renderer. One
intent becomes one JSON command dispatched through a caller-supplied
transport (the Qt 3D background widget); the bridge never builds JavaScript,
never renders, and never lets a failure escape as an exception — every path
returns ``{"success": False, "error": ..., "message": ...}`` so the face/UI
stays usable (STEP 8). Asset bytes travel base64-encoded on SHOW only: one
object, ~72 KB — ponytail: switch to a file URL fetch past ~500 KB.
"""

import base64
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

from .assets import AssetFormat, AssetRegistry, AssetStatus
from .concepts import UnknownConceptError
from .intent import IntentAction, VisualIntent
from .world_model import Entity, UnknownEntityError, VisualWorldModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SUPPORTED_ACTIONS = frozenset(
    {
        IntentAction.SHOW,
        IntentAction.HIDE,
        IntentAction.ROTATE,
        IntentAction.ZOOM,
        IntentAction.FOCUS,
        IntentAction.RETURN_TO_FACE,
    }
)

_GLB_HEADER = 12
_GLB_MAGIC = b"glTF"
_GLB_VERSION = 2


class _BridgeError(Exception):
    """Internal signal carrying a structured failure result."""

    def __init__(self, result: dict) -> None:
        super().__init__(result.get("error", "visual_failure"))
        self.result = result


def _fail(error: str, message: str) -> dict:
    return {"success": False, "error": error, "message": message}


class VisualBridge:
    """Resolves a VisualIntent against the world model and asset registry,
    then dispatches exactly one renderer command per call."""

    def __init__(
        self,
        world: VisualWorldModel,
        registry: AssetRegistry,
        dispatch: Callable[[dict], None],
    ) -> None:
        self.world = world
        self.registry = registry
        self._dispatch = dispatch

    def execute(self, intent: VisualIntent) -> dict:
        try:
            command = self._command(intent)
            self._dispatch(command)
        except _BridgeError as failure:
            return failure.result
        except Exception as exc:  # transport blew up — report, never raise
            return _fail("renderer_unavailable", f"could not reach the 3D scene: {exc}")
        result = {"success": True, "action": command["action"]}
        if "entity" in command:
            result["entity_id"] = command["entity"]["id"]
        if "asset" in command:
            result["asset_id"] = command["asset"]["asset_id"]
        return result

    # ── command builders ────────────────────────────────────────────────────

    def _command(self, intent: VisualIntent) -> dict:
        action = intent.action
        if action not in SUPPORTED_ACTIONS:
            raise _BridgeError(_fail("unsupported_action", f"{action.value!r} is not wired to the renderer yet"))
        if action is IntentAction.RETURN_TO_FACE:
            return {"action": action.value}

        if action is IntentAction.SHOW:
            # Asset first: a failed SHOW must leave no orphan entity behind.
            concept_id = self._show_concept(intent)
            asset, payload = self._select_asset(concept_id)
            entity = self._resolve(intent)
            self.world.set_visible(entity.id, True)
            return {
                "action": action.value,
                "entity": {"id": entity.id, "concept": entity.concept},
                "asset": asset,
                "transform": deepcopy(entity.transform),
                "data_base64": payload,
            }

        entity = self._resolve(intent)
        command = {"action": action.value, "entity": {"id": entity.id, "concept": entity.concept}}
        if action is IntentAction.HIDE:
            self.world.set_visible(entity.id, False)
        elif action in (IntentAction.ROTATE, IntentAction.ZOOM):
            command["parameters"] = dict(intent.parameters)
        return command

    def _show_concept(self, intent: VisualIntent) -> str:
        if intent.entity_id is not None:
            try:
                return self.world.get_entity(intent.entity_id).concept
            except UnknownEntityError as exc:
                raise _BridgeError(_fail("unknown_entity", str(exc))) from exc
        if intent.concept_id is None:
            raise _BridgeError(_fail("unknown_entity", "'show' needs an entity_id or concept_id"))
        return intent.concept_id

    def _resolve(self, intent: VisualIntent) -> Entity:
        if intent.entity_id is not None:
            try:
                return self.world.get_entity(intent.entity_id)
            except UnknownEntityError as exc:
                raise _BridgeError(_fail("unknown_entity", str(exc))) from exc
        concept_id = intent.concept_id
        if concept_id is None:
            raise _BridgeError(_fail("unknown_entity", f"{intent.action.value!r} needs an entity_id or concept_id"))
        live = [row for row in self.world.to_dict()["entities"] if row["concept"] == concept_id]
        if live:
            return self.world.get_entity(live[0]["id"])
        if intent.action is IntentAction.SHOW:
            try:
                return self.world.create_entity(concept_id)
            except UnknownConceptError as exc:
                raise _BridgeError(_fail("unknown_concept", str(exc))) from exc
        raise _BridgeError(_fail("unknown_entity", f"no {concept_id!r} is on screen"))

    # ── asset selection ─────────────────────────────────────────────────────

    def _select_asset(self, concept_id: str) -> tuple[dict, str]:
        try:
            asset = self.registry.find_for_concept(concept_id)
        except UnknownConceptError as exc:
            raise _BridgeError(_fail("unknown_concept", str(exc))) from exc
        if asset.status is not AssetStatus.AVAILABLE or not asset.path:
            raise _BridgeError(
                _fail("missing_asset", f"no 3D asset is available for {concept_id!r} (status={asset.status.value})")
            )
        if asset.format is not AssetFormat.GLB:
            raise _BridgeError(
                _fail("invalid_asset", f"asset {asset.asset_id!r} is {asset.format.value}; the renderer loads glb")
            )
        try:
            data = (PROJECT_ROOT / asset.path).read_bytes()
        except OSError as exc:
            raise _BridgeError(_fail("asset_load_failed", f"could not read {asset.path}: {exc}")) from exc
        if (
            len(data) < _GLB_HEADER
            or data[:4] != _GLB_MAGIC
            or int.from_bytes(data[4:8], "little") != _GLB_VERSION
            or int.from_bytes(data[8:12], "little") != len(data)
        ):
            raise _BridgeError(_fail("asset_load_failed", f"asset {asset.asset_id!r} is not a valid glTF 2.0 binary"))
        payload = {"asset_id": asset.asset_id, "path": asset.path, "format": asset.format.value}
        return payload, base64.b64encode(data).decode("ascii")
