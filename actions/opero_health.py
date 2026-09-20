"""Read-only operational health report."""
from __future__ import annotations

import json

from core.health import health_summary
from core.recovery import history


def opero_health(parameters: dict, **_kwargs) -> str:
    """Report health and recent recovery changes without altering anything."""
    mode = str(parameters.get("mode", "status")).lower()
    if mode == "recovery_history":
        return json.dumps([record.__dict__ for record in history()], indent=2)
    if mode != "status":
        return "Use mode 'status' or 'recovery_history'."
    return json.dumps(health_summary(), indent=2)


TOOL = {
    "name": "opero_health",
    "description": "Check OPERO configuration and recovery status without changing anything.",
    "parameters": {
        "type": "OBJECT",
        "properties": {"mode": {"type": "STRING", "enum": ["status", "recovery_history"]}},
    },
    "handler": opero_health,
}
