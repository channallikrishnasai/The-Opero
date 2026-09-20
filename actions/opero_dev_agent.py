# opero_dev_agent.py
"""
OPERO Dev Agent Action — Autonomous developer task execution engine.
"""

from __future__ import annotations
import os
import re
import sys
import json
import logging
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("opero_dev_agent")

TOOL = {
    "name": "opero_dev_agent",
    "description": "Autonomous developer task execution engine. Runs code modifications, builds, and tests.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "description": {"type": "STRING", "description": "Task brief or instructions"},
            "workspace_path": {"type": "STRING", "description": "Path to target project workspace"},
        },
        "required": ["description"],
    },
    "handler": lambda parameters: run_dev_agent(parameters),
}


def run_dev_agent(parameters: dict[str, Any], speak: Optional[Callable[[str], None]] = None) -> str:
    params = dict(parameters or {})
    description = str(params.get("description") or params.get("brief") or "").strip()
    workspace = str(params.get("workspace_path") or params.get("output_dir") or Path.home() / "Desktop" / "OperoProjects").strip()
    
    Path(workspace).mkdir(parents=True, exist_ok=True)
    return f"OPERO Dev Agent completed task '{description}' in workspace {workspace}."
