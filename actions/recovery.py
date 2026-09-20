"""Review-first recovery controls for OPERO-managed backups."""
from __future__ import annotations

import json

from core import confirm
from core.recovery import history, rollback


def recovery(parameters: dict, **_kwargs) -> str:
    """Inspect recovery history or restore one recorded backup after confirmation."""
    action = str(parameters.get("action", "history")).strip().lower()
    if action == "history":
        return json.dumps([record.__dict__ for record in history()], indent=2)
    if action != "rollback":
        return "Use action 'history' or 'rollback'."
    change_id = str(parameters.get("change_id", "latest")).strip() or "latest"

    def _restore() -> str:
        restored = rollback(change_id)
        return f"Recovery change {restored.change_id} rolled back." if restored else "No applied recovery change is available to roll back."

    return confirm.request("recovery-rollback", "Restore source backup", f"Restore recovery backup '{change_id}'?", _restore)


TOOL = {
    "name": "recovery",
    "description": "Inspect OPERO recovery history or restore a recorded local backup after on-screen confirmation.",
    "parameters": {"type": "OBJECT", "properties": {
        "action": {"type": "STRING", "description": "history | rollback"},
        "change_id": {"type": "STRING", "description": "Recovery change ID or latest"},
    }},
    "handler": recovery,
}
