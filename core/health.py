"""Read-only health checks used by OPERO's recovery workflow."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class HealthCheck:
    name: str
    ok: bool
    detail: str


def run_health_checks() -> list[HealthCheck]:
    """Return non-invasive checks; this function never changes the machine."""
    key_available = bool(os.environ.get("GEMINI_API_KEY") or (BASE_DIR / "config" / "api_keys.json").is_file())
    return [
        HealthCheck("project_root", (BASE_DIR / "main.py").is_file(), "main.py is present"),
        HealthCheck("gemini_key", key_available, "API key configured" if key_available else "Configure a Gemini API key in Settings."),
        HealthCheck("actions", (BASE_DIR / "actions").is_dir(), "Bundled actions directory is present"),
        HealthCheck("recovery", (BASE_DIR / "core" / "recovery.py").is_file(), "Review-first recovery is available"),
    ]


def health_summary() -> dict:
    checks = run_health_checks()
    return {"healthy": all(item.ok for item in checks), "checks": [asdict(item) for item in checks]}
