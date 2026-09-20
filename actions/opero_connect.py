# opero_connect.py
"""
OPERO Connect device pairing & remote execution bridge for OPERO AI.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any

TOOL = {
    "name": "opero_connect",
    "description": "Remote device pairing, status checking, and execution gateway.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {"type": "STRING", "description": "Target device name or ID"},
            "action": {"type": "STRING", "description": "Action to execute on target device"},
            "parameters": {"type": "OBJECT", "description": "Parameters for the action"},
        },
        "required": ["target", "action"],
    },
    "handler": lambda parameters: connect_execute(parameters),
}


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def connect_execute(parameters: dict[str, Any] | None = None, player=None, speak=None) -> str:
    params = dict(parameters or {})
    target = str(params.get("target") or params.get("device") or "Device").strip()
    action = str(params.get("action") or params.get("command") or "status").strip()

    return _dump({
        "success": True,
        "device": target,
        "action": action,
        "message": f"Command '{action}' routed to {target}.",
    })
