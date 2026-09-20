import json


def test_health_summary_has_named_checks():
    from core.health import health_summary

    report = health_summary()
    assert isinstance(report["healthy"], bool)
    assert {check["name"] for check in report["checks"]} >= {"project_root", "actions", "recovery"}


def test_health_action_is_read_only_report():
    from actions.opero_health import opero_health

    payload = json.loads(opero_health({"mode": "status"}))
    assert "checks" in payload
