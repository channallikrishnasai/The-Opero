"""Tests for desktop perception (OS/browser boundaries mocked — no real screen, browser, or GPU)."""

import json
import sys
import types

from core.perception import (
    WindowInfo,
    capture_screen,
    get_active_window,
    get_screen_context,
    probe_browser,
)


class _FakeShot:
    size = (2, 2)
    rgb = bytes(12)  # 2x2 RGB


class _FakeMssSession:
    monitors = [{"left": 0, "top": 0, "width": 2, "height": 2}]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def grab(self, spec):
        return _FakeShot()


def _fake_mss() -> types.SimpleNamespace:
    return types.SimpleNamespace(mss=lambda: _FakeMssSession())


def test_screen_capture_can_be_called_safely(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "mss", _fake_mss())
    capture = capture_screen()
    assert capture.png.startswith(b"\x89PNG")
    assert (capture.width, capture.height) == (2, 2)
    meta = capture.to_dict()
    assert meta["width"] == 2 and meta["height"] == 2
    assert "png" not in meta  # image bytes never enter serialized contexts


def test_active_window_has_stable_schema(monkeypatch) -> None:
    monkeypatch.setattr("core.perception.windows._active_raw", lambda: ("Fake Editor", 4242))
    monkeypatch.setattr("core.perception.windows._process_name", lambda pid: "editor.exe")
    active = get_active_window()
    assert active is not None
    payload = active.to_dict()
    assert list(payload) == ["title", "process", "pid"]
    assert payload == {"title": "Fake Editor", "process": "editor.exe", "pid": 4242}
    assert isinstance(payload["pid"], int)

    monkeypatch.setattr("core.perception.windows._active_raw", lambda: None)
    assert get_active_window() is None


def test_perception_context_serializes(monkeypatch) -> None:
    monkeypatch.setattr("core.perception.windows._active_raw", lambda: ("Fake Window", 1))
    monkeypatch.setattr("core.perception.windows._enumerate_raw", lambda: [("Fake Window", 1), ("Other Window", 2)])
    monkeypatch.setattr("core.perception.windows._process_name", lambda pid: "fake.exe")
    monkeypatch.setattr("core.perception.context._integration_available", lambda: False)

    payload = get_screen_context().to_dict()
    json.dumps(payload)  # deterministic, JSON-serializable
    assert set(payload) == {"timestamp", "screen", "windows", "browser"}
    assert payload["screen"] is None  # no capture unless explicitly requested
    assert set(payload["windows"]) == {"active_window", "windows"}
    assert payload["windows"]["active_window"] == {"title": "Fake Window", "process": "fake.exe", "pid": 1}
    assert len(payload["windows"]["windows"]) == 2
    assert payload["browser"]["detected"] is False
    assert payload["browser"]["integration_available"] is False

    monkeypatch.setitem(sys.modules, "mss", _fake_mss())
    captured = get_screen_context(capture=True).to_dict()
    assert captured["screen"]["width"] == 2
    assert "png" not in captured["screen"]
    assert json.dumps(captured)


def test_browser_capability_detection_when_integration_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("core.perception.context._integration_available", lambda: False)
    active = WindowInfo(title="Google Chrome", process="chrome.exe", pid=77)
    probe = probe_browser(active)
    assert probe.detected is True
    assert probe.name == "chrome"
    assert probe.pid == 77
    assert probe.integration_available is False
    assert probe.capabilities == {
        "enumerate_tabs": False,
        "inspect_page": False,
        "navigate": False,
        "click": False,
        "type": False,
    }

    monkeypatch.setattr("core.perception.context._integration_available", lambda: True)
    assert all(probe_browser(active).capabilities.values())

    # No active browser window: structured result, no crash.
    monkeypatch.setattr("core.perception.windows._active_raw", lambda: None)
    assert probe_browser().detected is False
