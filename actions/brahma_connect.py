from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Callable

# brahma_connect.service is a Brahma-specific package not present in Opero.
# We provide a no-op stub so the module loads cleanly.
try:
    from brahma_connect.service import get_service as _get_service_real  # type: ignore
except ModuleNotFoundError:
    def _get_service_real(base_dir):  # type: ignore
        return None


def get_service(base_dir=None):
    return _get_service_real(base_dir)


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()
_SERVICE_PROVIDER: Callable[[], Any] | None = None


def set_service_provider(provider: Callable[[], Any] | None) -> None:
    global _SERVICE_PROVIDER
    _SERVICE_PROVIDER = provider


from core.logger import get_logger
log = get_logger(__name__)


_GATEWAY_LAUNCHED = False


def _service():
    global _GATEWAY_LAUNCHED
    if _SERVICE_PROVIDER is not None:
        return _SERVICE_PROVIDER()
    svc = get_service(BASE_DIR)
    # Serve the local gateway lazily on the first device command so companion
    # devices can pair/connect (it listens on 0.0.0.0:8765). start_background()
    # is already a no-op while its thread is alive; the module flag just keeps
    # us out of this block during the brief window before is_running() flips.
    if svc is not None and not svc.is_running() and not _GATEWAY_LAUNCHED:
        try:
            svc.start_background()
            _GATEWAY_LAUNCHED = True
            cfg = getattr(getattr(svc, "gateway", None), "config", None)
            log.info("[brahma_connect] gateway serving on port %s", cfg.port if cfg else 8765)
        except Exception as e:
            _GATEWAY_LAUNCHED = False
            log.warning("[brahma_connect] gateway start failed: %s", e)
    return svc


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _fail(error: str, error_code: str, *, device: str | None = None, action: str | None = None, **extra: Any) -> str:
    payload: dict[str, Any] = {
        "success": False,
        "error": error,
        "error_code": error_code,
    }
    if device is not None:
        payload["device"] = device
    if action is not None:
        payload["action"] = action
    payload.update(extra)
    return _dump(payload)


def _success(**payload: Any) -> str:
    payload.setdefault("success", True)
    return _dump(payload)


def _normalize_target(parameters: dict[str, Any] | None) -> str:
    params = parameters or {}
    return str(
        params.get("device")
        or params.get("target")
        or params.get("device_id")
        or params.get("name")
        or params.get("query")
        or ""
    ).strip()


def _execute_action_name(parameters: dict[str, Any] | None) -> str:
    params = parameters or {}
    return str(params.get("action") or params.get("command") or "").strip()


def _required_params_for_action(action: str) -> list[str]:
    action = (action or "").strip().lower()
    return {
        "launch_app": ["app_name"],
        "close_app": ["app_name"],
        "open_url": ["url"],
        "capture_screen": [],
        "take_photo": [],
        "clipboard_get": [],
        "clipboard_set": ["text"],
        "send_file": ["file_path"],
        "receive_file": ["destination"],
        "media_play": [],
        "media_pause": [],
        "volume_set": ["value"],
        "notification_list": [],
        "get_battery": [],
        "get_device_info": [],
        "mouse_move": ["x", "y"],
        "keyboard_type": ["text"],
        "ui_tap": ["x", "y"],
        "ui_swipe": ["x1", "y1", "x2", "y2"],
        "ui_type": ["text"],
    }.get(action, [])


def _required_capabilities_for_action(action: str) -> list[str]:
    action = (action or "").strip().lower()
    return {
        "launch_app": ["launch_app"],
        "close_app": ["launch_app"],
        "open_url": ["launch_app"],
        "capture_screen": ["screen_capture"],
        "take_photo": ["camera"],
        "clipboard_get": ["clipboard"],
        "clipboard_set": ["clipboard"],
        "send_file": ["files"],
        "receive_file": ["files"],
        "media_play": ["media"],
        "media_pause": ["media"],
        "volume_set": ["media"],
        "notification_list": ["notifications"],
        "get_battery": ["battery"],
        "get_device_info": ["device_info"],
        "mouse_move": ["mouse"],
        "keyboard_type": ["keyboard"],
    }.get(action, [])


def _format_devices(devices: list[dict[str, Any]]) -> str:
    items = []
    for device in devices:
        battery = device.get("battery")
        battery_text = f"{battery}%" if battery is not None else "Unknown"
        items.append({
            "device_id": device.get("device_id", ""),
            "name": device.get("name", "Unknown Device"),
            "platform": device.get("platform", "unknown"),
            "online": bool(device.get("online", False)),
            "battery": battery,
            "battery_text": battery_text,
            "capabilities": list(device.get("capabilities") or []),
        })
    return _dump({"success": True, "count": len(items), "devices": items})


def _single_or_ambiguous(matches: list[dict[str, Any]], *, device_label: str, action: str) -> str:
    if not matches:
        return _fail(
            f"No device matches '{device_label}'.",
            "DEVICE_NOT_FOUND",
            device=device_label,
            action=action,
        )
    if len(matches) > 1:
        return _dump({
            "success": False,
            "error": "Multiple devices matched the request.",
            "error_code": "MULTIPLE_DEVICES",
            "device": device_label,
            "action": action,
            "matches": matches,
        })
    return _dump({"success": True, "device": matches[0]})


def connect_list_devices(parameters: dict[str, Any] | None = None, player=None, speak=None) -> str:
    try:
        service = _service()
        return _format_devices(service.list_devices())
    except Exception as exc:
        return _fail(str(exc), "GATEWAY_UNAVAILABLE", action="connect_list_devices")


def connect_get_device(parameters: dict[str, Any] | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    target = _normalize_target(params)
    if not target:
        return _fail("A device name or id is required.", "MISSING_PARAMETERS", action="connect_get_device")
    try:
        service = _service()
        direct = service.get_device(target)
        if direct:
            return _dump({"success": True, "device": direct})
        matches = service.resolve_devices(target)
        if not matches:
            return _fail(f"No device matches '{target}'.", "DEVICE_NOT_FOUND", device=target, action="connect_get_device")
        if len(matches) > 1:
            return _dump({
                "success": False,
                "error": "Multiple devices matched the request.",
                "error_code": "MULTIPLE_DEVICES",
                "device": target,
                "action": "connect_get_device",
                "matches": matches,
            })
        return _dump({"success": True, "device": matches[0]})
    except Exception as exc:
        return _fail(str(exc), "GATEWAY_UNAVAILABLE", device=target, action="connect_get_device")


def connect_get_capabilities(parameters: dict[str, Any] | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    target = _normalize_target(params)
    if not target:
        return _fail("A device name or id is required.", "MISSING_PARAMETERS", action="connect_get_capabilities")
    try:
        service = _service()
        result = service.get_capabilities(target)
        if not result.get("success", False):
            return _dump(result)
        device = result.get("device") or {}
        return _dump({
            "success": True,
            "device": {
                "device_id": device.get("device_id", ""),
                "name": device.get("name", "Unknown Device"),
                "platform": device.get("platform", "unknown"),
                "online": bool(device.get("online", False)),
            },
            "capabilities": list(result.get("capabilities") or []),
            "permissions": list(result.get("permissions") or []),
        })
    except Exception as exc:
        return _fail(str(exc), "GATEWAY_UNAVAILABLE", device=target, action="connect_get_capabilities")


def connect_pair_device(parameters: dict[str, Any] | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    try:
        service = _service()
        pending_id = str(params.get("pending_id") or "").strip()
        if pending_id:
            result = asyncio.run(service.approve_pending_request(pending_id))
            return _dump(result)

        device_name = str(params.get("device_name") or params.get("name") or "Unknown Device").strip()
        platform = str(params.get("platform") or "unknown").strip()
        offer = service.create_pairing_offer(device_name=device_name, platform=platform)
        return _dump({
            "success": True,
            "pairing": offer,
            "message": "Share the pairing code or QR payload with the device agent.",
        })
    except Exception as exc:
        return _fail(str(exc), "GATEWAY_UNAVAILABLE", action="connect_pair_device")


def connect_disconnect_device(parameters: dict[str, Any] | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    target = _normalize_target(params)
    if not target:
        return _fail("A device name or id is required.", "MISSING_PARAMETERS", action="connect_disconnect_device")
    reason = str(params.get("reason") or "Disconnected by Brahma").strip()
    try:
        service = _service()
        result = asyncio.run(service.disconnect_device(target, reason=reason))
        return _dump(result)
    except Exception as exc:
        return _fail(str(exc), "GATEWAY_UNAVAILABLE", device=target, action="connect_disconnect_device")


def connect_execute(parameters: dict[str, Any] | None = None, player=None, speak=None) -> str:
    params = dict(parameters or {})
    target = _normalize_target(params)
    action = _execute_action_name(params)
    if not target:
        return _fail("A target device is required.", "MISSING_PARAMETERS", action="connect_execute")
    if not action:
        return _fail("An action name is required.", "MISSING_PARAMETERS", device=target, action="connect_execute")

    command_parameters = dict(params.get("parameters") or {})
    for key, value in params.items():
        if key not in {"device", "target", "device_id", "name", "query", "action", "command", "parameters"}:
            command_parameters.setdefault(key, value)

    missing_params = [key for key in _required_params_for_action(action) if not str(command_parameters.get(key, "")).strip()]
    if action == "launch_app" and not any(
        str(command_parameters.get(key, "")).strip() for key in ("app_name", "package", "package_name")
    ):
        missing_params = ["app_name"]
    if missing_params:
        return _dump({
            "success": False,
            "device": target,
            "action": action,
            "error": f"Missing required parameters: {', '.join(missing_params)}.",
            "error_code": "MISSING_PARAMETERS",
            "missing_parameters": missing_params,
        })

    required_capabilities = _required_capabilities_for_action(action)
    if required_capabilities:
        command_parameters = dict(command_parameters)
        command_parameters["required_capabilities"] = required_capabilities

    try:
        service = _service()
        result = service.route_command(target, action, command_parameters)
        if not isinstance(result, dict):
            return _dump({
                "success": True,
                "device": target,
                "action": action,
                "data": result,
            })

        result.setdefault("device", target)
        result.setdefault("action", action)
        if result.get("success", False):
            if "data" not in result and "result" in result:
                result["data"] = result.pop("result")
            return _dump(result)

        error_code = str(result.get("error_code") or "COMMAND_FAILED")
        if error_code == "DEVICE_OFFLINE":
            result["error"] = result.get("error") or f"Your {target} is currently offline."
        return _dump(result)
    except Exception as exc:
        return _fail(str(exc), "GATEWAY_UNAVAILABLE", device=target, action=action)

def device_gateway(parameters: dict | None = None, player=None, speak=None) -> str:
    """Paired-device management entry point for the OPERO tool layer."""
    params = dict(parameters or {})
    action = str(params.get("action") or "list").strip().lower()
    routes = {
        "list": connect_list_devices,
        "devices": connect_list_devices,
        "get": connect_get_device,
        "info": connect_get_device,
        "capabilities": connect_get_capabilities,
        "pair": connect_pair_device,
        "disconnect": connect_disconnect_device,
        "execute": connect_execute,
        "command": connect_execute,
    }
    fn = routes.get(action, connect_execute)
    return fn(params, player=player, speak=speak)


# ── OPERO tool registration ───────────────────────────────────────────────────
TOOL = {
    "name": "device_gateway",
    "description": (
        "Paired-device gateway: list, pair, inspect and disconnect remote devices, query their "
        "capabilities, and run commands on them (launch_app, open_url, capture_screen, clipboard, "
        "media, volume, battery, UI taps...)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "list (default) | pair | get | capabilities | disconnect | execute",
            },
            "target": {"type": "STRING", "description": "Target device name or ID."},
            "device": {"type": "STRING", "description": "Alias for target."},
            "command": {"type": "STRING", "description": "Command to run for action=execute (alias of action)."},
            "parameters": {"type": "OBJECT", "description": "Parameters for the command being executed."},
        },
        "required": ["action"],
    },
    "handler": device_gateway,
}
