"""Task-journal action for reporting recent OPERO work."""
from __future__ import annotations

import json

from core.task_manager import journal


def task_status(parameters: dict, **_kwargs) -> str:
    """Return a privacy-safe recent task report, with no side effects."""
    try:
        limit = int(parameters.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 50))
    return json.dumps(journal.recent(limit), indent=2)


TOOL = {
    "name": "task_status",
    "description": "Show recent OPERO action states, results, and failures without changing anything.",
    "parameters": {"type": "OBJECT", "properties": {"limit": {"type": "INTEGER", "description": "1 to 50; defaults to 10"}}},
    "handler": task_status,
}
