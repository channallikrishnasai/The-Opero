"""Phase 7B: cursor control actions — dispatch wiring, waypoint parsing,
tween selection, honest screen_find refusal, targeted window-op messages.
No real mouse/keyboard input is performed: every case below returns before
pyautogui is touched (or raises first)."""
from actions.computer_control import (
    TOOL, _EASES, _button, _fail_unresolved, _parse_points, _tween,
    _window_op, computer_control,
)


# ── dispatch safety rails ────────────────────────────────────────────────────

def test_no_action_is_refused():
    assert computer_control({}) == "No action specified for computer_control."


def test_unknown_action_is_named_back():
    assert "Unknown action: 'levitate'" in computer_control({"action": "levitate"})


def test_move_without_location_says_what_it_needs():
    out = computer_control({"action": "move"})
    assert out.startswith("move needs a location")
    assert "anchor" in out


def test_unresolved_anchor_fails_loudly_never_guesses():
    out = computer_control({"action": "move", "anchor": "nowhere special"})
    assert out.startswith("Could not resolve coordinates")
    assert "explicit x,y" in out


def test_screen_find_and_screen_click_declare_unavailable_honestly():
    for action in ("screen_find", "screen_click"):
        out = computer_control({"action": action, "description": "the blue button"})
        assert out.startswith("UNAVAILABLE:")
        assert "screen_process" in out          # points at the real path
        assert "NOT_FOUND" not in out           # never a fake negative


def test_window_ops_need_a_title_fragment():
    for action in ("window_minimize", "window_maximize", "window_restore", "window_close"):
        out = computer_control({"action": action})
        assert "needs a title fragment" in out


def test_window_close_with_no_match_reports_nothing_found():
    out = computer_control({"action": "window_close",
                            "title": "ZZNoSuchWindowZZ-7b"})
    assert "No window matching" in out


def test_window_close_poll_invalidates_the_world_cache(monkeypatch):
    """Regression: the close loop used to read a TTL-cached window list and
    reported 'still there' after the window was already gone."""
    from types import SimpleNamespace

    class _DyingWorld:
        def __init__(self):
            self.alive = True
            self.invalidates = 0

        def find_windows(self, query):
            if not self.alive:
                return []
            return [SimpleNamespace(title="Fake Cmd", process="cmd.exe",
                                    rect=(0, 0, 100, 100), state="normal",
                                    hwnd=0x12345, pid=1)]

        def invalidate(self):
            self.invalidates += 1
            self.alive = False            # probe re-runs and sees it gone

    dying = _DyingWorld()
    monkeypatch.setattr("core.world_model.world", lambda: dying)
    out = _window_op("close", "cmd")
    assert "verified: title gone" in out
    assert dying.invalidates >= 1


# ── parameter helpers ────────────────────────────────────────────────────────

def test_button_defaults_and_falls_back_to_left():
    assert _button({}) == "left"
    assert _button({"button": "right"}) == "right"
    assert _button({"button": "middle"}) == "middle"
    assert _button({"button": "mouse4"}) == "left"


def test_parse_points_accepts_lists_dicts_and_strings():
    assert _parse_points([[1, 2], [3, 4]]) == [(1, 2), (3, 4)]
    assert _parse_points("10,20 30,40") == [(10, 20), (30, 40)]
    assert _parse_points("10,20 -5, 6") == [(10, 20), (-5, 6)]
    assert _parse_points([{"x": 5, "y": 6}]) == [(5, 6)]
    assert _parse_points([[1, 2], "bad", {"x": None}]) == [(1, 2)]
    assert _parse_points(None) == []
    assert _parse_points([]) == []


def test_tween_eases_map_to_pyautogui_tweens():
    assert set(_EASES) == {"linear", "ease_out", "ease_in", "ease_in_out"}
    assert _tween("linear") is None             # no easing, plain move
    for name in ("ease_out", "ease_in", "ease_in_out"):
        assert callable(_tween(name))
    assert callable(_tween("bogus"))            # unknown → default ease-out


def test_fail_unresolved_formats_the_call_site():
    out = _fail_unresolved({"anchor": "top-left", "window": "Notepad"})
    assert "top-left" in out and "Notepad" in out
    out = _fail_unresolved({"anchor": "center"})
    assert "(none)" in out


# ── tool declaration stays honest ────────────────────────────────────────────

def test_tool_declares_new_actions_and_unavailable_screen_ops():
    desc = TOOL["description"]
    assert "minimize" in desc and "anchor" in desc
    assert "UNAVAILABLE" in desc and "screen_process" in desc
    props = TOOL["parameters"]["properties"]
    for key in ("anchor", "window", "monitor", "dx", "dy", "points",
                "duration", "ease", "button"):
        assert key in props
    actions = props["action"]["description"]
    for name in ("move_relative", "move_path", "mouse_down", "key_down",
                 "drag", "window_restore"):
        assert name in actions
