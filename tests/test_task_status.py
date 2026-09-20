import json


def test_task_status_returns_recent_records():
    from actions.task_status import task_status
    from core.task_manager import journal

    journal.create("Visibility test", kind="test")
    payload = json.loads(task_status({"limit": 1}))
    assert len(payload) == 1
    assert payload[0]["label"] == "Visibility test"


def test_task_status_limits_invalid_values():
    from actions.task_status import task_status

    assert isinstance(json.loads(task_status({"limit": "not-a-number"})), list)
