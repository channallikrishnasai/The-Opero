"""Phase 7B: spatial targeting — explicit coords beat anchors, anchors resolve
against windows/monitors via the world model, unresolvable targets refuse.
Plus computer_settings' machine-scoped search and virtual-desktop detection."""
from types import SimpleNamespace

from actions import computer_control as cc
from actions import computer_settings as cs


def _win(title, rect, process="app.exe"):
    return SimpleNamespace(title=title, process=process, rect=rect,
                           state="normal", hwnd=1, pid=1)


class _FakeWorld:
    def __init__(self, windows=(), monitors=()):
        self._windows = list(windows)
        self._monitors = list(monitors)

    def find_windows(self, query):
        toks = str(query).lower().split()
        return [w for w in self._windows
                if all(t in f"{w.title} {w.process}".lower() for t in toks)]

    def windows(self):
        return list(self._windows)

    def monitors(self):
        return list(self._monitors)

    def primary_rect(self):
        for m in self._monitors:
            if getattr(m, "primary", False):
                return tuple(m.rect)
        return tuple(self._monitors[0].rect) if self._monitors else None


def _patch_world(monkeypatch, fake):
    monkeypatch.setattr("core.world_model.world", lambda: fake)


# ── _resolve_point priority: explicit coords > anchor > current ──────────────

def test_explicit_xy_win_over_any_anchor(monkeypatch):
    _patch_world(monkeypatch, _FakeWorld())       # world never consulted
    assert cc._resolve_point({"x": 10, "y": 20, "anchor": "center"}) == ("ok", 10, 20)
    assert cc._resolve_point({"x": "10", "y": "20"}) == ("ok", 10, 20)


def test_no_location_means_click_at_current_cursor(monkeypatch):
    _patch_world(monkeypatch, _FakeWorld())
    assert cc._resolve_point({}) == ("current", None, None)
    assert cc._resolve_point({"x": 10}) == ("current", None, None)   # y missing


def test_anchor_resolves_against_window_rect(monkeypatch):
    note = _win("Notepad", (100, 200, 300, 400))
    _patch_world(monkeypatch, _FakeWorld(windows=[note]))
    status, x, y = cc._resolve_point({"window": "notepad", "anchor": "top-left"})
    assert (status, x, y) == ("ok", 108, 208)     # nudged 8px inside the rect


def test_spatial_window_phrase_picks_the_right_window(monkeypatch):
    left = _win("Chrome", (0, 0, 400, 300))
    right = _win("Edge", (800, 0, 1200, 300))
    _patch_world(monkeypatch, _FakeWorld(windows=[left, right]))
    status, x, y = cc._resolve_point(
        {"window": "the window on the right", "anchor": "center"})
    assert status == "ok"
    assert (x, y) == (1000, 150)                  # right window's center


def test_anchor_without_window_falls_back_to_monitor(monkeypatch):
    mon = SimpleNamespace(index=0, rect=(0, 0, 1920, 1080), primary=True)
    _patch_world(monkeypatch, _FakeWorld(monitors=[mon]))
    assert cc._resolve_point({"anchor": "center"}) == ("ok", 960, 540)
    assert cc._resolve_point({"anchor": "top-left"}) == ("ok", 8, 8)


def test_monitor_index_out_of_range_uses_primary(monkeypatch):
    mon = SimpleNamespace(index=0, rect=(0, 0, 800, 600), primary=True)
    _patch_world(monkeypatch, _FakeWorld(monitors=[mon]))
    status, x, y = cc._resolve_point({"anchor": "center", "monitor": 5})
    assert (status, x, y) == ("ok", 400, 300)


def test_unmatched_window_refuses_instead_of_guessing(monkeypatch):
    _patch_world(monkeypatch, _FakeWorld(windows=[]))
    assert cc._resolve_point({"window": "GhostApp", "anchor": "center"})[0] == "unresolved"


def test_unrecognized_anchor_phrase_refuses(monkeypatch):
    mon = SimpleNamespace(index=0, rect=(0, 0, 800, 600), primary=True)
    _patch_world(monkeypatch, _FakeWorld(monitors=[mon]))
    assert cc._resolve_point({"anchor": "somewhere dramatic"})[0] == "unresolved"


def test_dispatch_reports_unresolved_anchor_with_guidance(monkeypatch):
    _patch_world(monkeypatch, _FakeWorld(windows=[]))
    out = cc.computer_control({"action": "click", "window": "GhostApp",
                               "anchor": "center"})
    assert out.startswith("Could not resolve coordinates")


def test_dispatch_click_at_explicit_coords_never_touches_the_mouse(monkeypatch):
    seen = {}
    monkeypatch.setattr(cc, "_click",
                        lambda x=None, y=None, button="left", clicks=1:
                        seen.update(x=x, y=y, button=button) or "ok")
    out = cc.computer_control({"action": "right_click", "x": 5, "y": 6,
                               "button": "middle"})
    assert out == "ok"
    assert seen == {"x": 5, "y": 6, "button": "right"}   # right_click wins


def test_dispatch_drag_honors_button(monkeypatch):
    seen = {}
    monkeypatch.setattr(cc, "_drag",
                        lambda x1, y1, x2, y2, duration=0.5, button="left":
                        seen.update(button=button) or "dragged")
    out = cc.computer_control({"action": "drag", "x1": 0, "y1": 0, "x2": 9,
                               "y2": 9, "button": "right"})
    assert out == "dragged" and seen["button"] == "right"


# ── computer_settings: machine-scoped search & virtual desktops ─────────────

def test_app_search_is_a_known_action():
    assert cs._detect_action("app_search")["action"] == "app_search"


def test_virtual_desktop_actions_are_detected_by_name_and_fuzzy():
    for name in cs._VD:
        assert cs._detect_action(name)["action"] == name
    assert cs._detect_action("virtual desktop new")["action"] == "virtual_desktop_new"


def test_settings_tool_documents_machine_search_and_desktops():
    desc = cs.TOOL["description"]
    assert "app_search" in desc
    assert "virtual desktops" in desc
    assert "web_search" in desc          # the never-send rule is stated
    actions = cs.TOOL["parameters"]["properties"]["action"]["description"]
    assert "virtual_desktop_new" in actions and "app_search" in actions


def test_app_search_targets_are_constrained_to_three():
    import inspect
    src = inspect.getsource(cs.app_search)
    for target in ("settings", "explorer", "page"):
        assert f'"{target}"' in src
    assert '"website"' not in src
