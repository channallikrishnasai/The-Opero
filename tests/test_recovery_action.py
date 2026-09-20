import json


def test_recovery_action_history_is_read_only(monkeypatch):
    import actions.recovery as action

    monkeypatch.setattr(action, "history", lambda: [])
    assert json.loads(action.recovery({"action": "history"})) == []


def test_recovery_action_rejects_unknown_mode():
    from actions.recovery import recovery

    assert recovery({"action": "erase_everything"}) == "Use action 'history' or 'rollback'."


def test_recovery_action_asks_for_confirmation(monkeypatch):
    import actions.recovery as action

    captured = {}
    def fake_confirm(key, title, message, callback):
        captured.update(key=key, title=title, message=message)
        return "Awaiting confirmation."

    monkeypatch.setattr(action.confirm, "request", fake_confirm)
    assert action.recovery({"action": "rollback", "change_id": "change-1"}) == "Awaiting confirmation."
    assert captured["key"] == "recovery-rollback"
    assert "change-1" in captured["message"]
