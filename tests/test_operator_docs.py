import json
from pathlib import Path


def test_example_configs_are_safe_placeholders():
    root = Path(__file__).resolve().parent.parent
    google = (root / "config" / "examples" / "google_oauth_client.example.json").read_text(encoding="utf-8")
    instagram = json.loads((root / "config" / "examples" / "instagram.example.json").read_text(encoding="utf-8"))
    assert "REPLACE_WITH" in google
    assert instagram["access_token"] == "YOUR_META_ACCESS_TOKEN"


def test_runbook_documents_release_checks():
    root = Path(__file__).resolve().parent.parent
    runbook = (root / "docs" / "OPERATOR_RUNBOOK.md").read_text(encoding="utf-8")
    assert "pytest" in runbook
    assert "opero_health" in runbook


def test_integration_guide_mentions_meta_messaging_limits():
    root = Path(__file__).resolve().parent.parent
    guide = (root / "docs" / "INTEGRATIONS.md").read_text(encoding="utf-8")
    assert "manage-messages" in guide
    assert "does not bypass" in guide
