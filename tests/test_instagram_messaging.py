import json


def test_status_reports_missing_configuration(monkeypatch, tmp_path):
    import actions.instagram_messaging as instagram

    monkeypatch.setattr(instagram, "CONFIG", tmp_path / "missing.json")
    assert "not connected" in instagram.execute({"action": "status"}).lower()


def test_requests_use_instagram_login_host(monkeypatch, tmp_path):
    import actions.instagram_messaging as instagram

    config = tmp_path / "instagram.json"
    config.write_text(json.dumps({"account_id": "account", "access_token": "token"}), encoding="utf-8")
    monkeypatch.setattr(instagram, "CONFIG", config)
    captured = {}

    class Reply:
        ok = True
        def json(self):
            return {"data": []}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, kwargs=kwargs)
        return Reply()

    monkeypatch.setattr(instagram.requests, "request", fake_request)
    assert instagram.execute({"action": "list"}) == "No Instagram conversations returned."
    assert captured["url"] == "https://graph.instagram.com/v25.0/account/conversations"
    assert captured["kwargs"]["params"] == {"access_token": "token"}


def test_tool_is_discoverable():
    from actions.instagram_messaging import TOOL

    assert TOOL["name"] == "instagram_messaging"


def test_read_requires_conversation_id(monkeypatch, tmp_path):
    import actions.instagram_messaging as instagram

    monkeypatch.setattr(instagram, "CONFIG", tmp_path / "missing.json")
    assert instagram.execute({"action": "read"}) == "conversation_id is required."


def test_read_formats_messages(monkeypatch, tmp_path):
    import actions.instagram_messaging as instagram

    config = tmp_path / "instagram.json"
    config.write_text(json.dumps({"account_id": "account", "access_token": "token"}), encoding="utf-8")
    monkeypatch.setattr(instagram, "CONFIG", config)

    class Reply:
        ok = True
        def json(self):
            return {"data": [{"from": {"id": "sender"}, "created_time": "today", "message": "Hello"}]}

    monkeypatch.setattr(instagram.requests, "request", lambda *args, **kwargs: Reply())
    assert instagram.execute({"action": "read", "conversation_id": "conversation"}) == "sender | today | Hello"
