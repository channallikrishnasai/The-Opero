from actions import gmail


def test_gmail_status_needs_no_optional_google_dependencies(monkeypatch, tmp_path):
    monkeypatch.setattr(gmail, "TOKEN_FILE", tmp_path / "gmail_token.json")
    assert "not connected" in gmail.execute({"action": "status"}).lower()


def test_gmail_tool_is_discoverable():
    assert gmail.TOOL["name"] == "gmail"
    assert callable(gmail.TOOL["handler"])


def test_disconnect_uses_confirmation(monkeypatch, tmp_path):
    import actions.gmail as gmail

    monkeypatch.setattr(gmail, "TOKEN_FILE", tmp_path / "token.json")
    captured = {}
    def fake_confirm(key, title, message, callback):
        captured.update(key=key, title=title, message=message)
        return "Awaiting confirmation."

    monkeypatch.setattr(gmail.confirm, "request", fake_confirm)
    assert gmail.execute({"action": "disconnect"}) == "Awaiting confirmation."
    assert captured["key"] == "gmail-disconnect"


def test_disconnect_removes_only_local_token(monkeypatch, tmp_path):
    import actions.gmail as gmail

    token = tmp_path / "token.json"
    token.write_text("token", encoding="utf-8")
    monkeypatch.setattr(gmail, "TOKEN_FILE", token)
    monkeypatch.setattr(gmail.confirm, "request", lambda _k, _t, _m, callback: callback())
    assert gmail.execute({"action": "disconnect"}) == "Local Gmail OAuth token removed."
    assert not token.exists()


def test_invalid_or_incomplete_requests_do_not_require_gmail_sdk(monkeypatch):
    import actions.gmail as gmail

    monkeypatch.setattr(gmail, "_service", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not connect")))
    assert "Unknown Gmail action" in gmail.execute({"action": "unknown"})
    assert gmail.execute({"action": "read"}) == "message_id is required."
    assert gmail.execute({"action": "draft", "to": "a@example.com"}) == "to, subject, and body are required."
