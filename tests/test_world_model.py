"""Phase 7B: ComputerWorld — TTL observation cache with explicit statuses,
spatial language, window picking. All probes injected; no real OS reads."""
import json
from types import SimpleNamespace

from core.perception.windows import MonitorInfo, WindowInfo
from core.world_model import (
    KNOWN, STALE, UNKNOWN, UNAVAILABLE,
    ComputerWorld, anchor_point, parse_spatial, pick_window,
)


def _win(title, process="app.exe", rect=(0, 0, 100, 100), hwnd=1):
    return SimpleNamespace(title=title, process=process, rect=rect,
                           state="normal", hwnd=hwnd, pid=1)


def _world():
    chrome = _win("Chrome - Tab", "chrome.exe", (0, 0, 400, 300), 11)
    note = _win("Notepad", "notepad.exe", (500, 100, 900, 500), 22)
    clock = {"t": 100.0}
    calls = {"windows": 0, "monitors": 0, "cursor": 0}

    def p_win():
        calls["windows"] += 1
        return {"windows": [chrome, note], "foreground": chrome}

    def p_mon():
        calls["monitors"] += 1
        return [MonitorInfo(index=0, rect=(0, 0, 1920, 1080), primary=True)]

    def p_cur():
        calls["cursor"] += 1
        return (123, 456)

    cw = ComputerWorld(ttl=5.0, clock=lambda: clock["t"],
                       probes={"windows": p_win, "monitors": p_mon, "cursor": p_cur})
    return cw, calls, clock, chrome, note


# ── cache lifecycle ──────────────────────────────────────────────────────────

def test_world_starts_unknown_and_refreshes_to_known():
    cw, calls, _, _, _ = _world()
    assert cw.status("windows") == UNKNOWN
    out = cw.refresh()
    assert out == {"windows": KNOWN, "monitors": KNOWN, "cursor": KNOWN}
    assert calls == {"windows": 1, "monitors": 1, "cursor": 1}


def test_world_ttl_expiry_and_invalidate():
    cw, calls, clock, _, _ = _world()
    cw.refresh()
    clock["t"] += 10.0                      # past the 5s TTL
    assert cw.status("windows") == STALE
    cw.refresh()
    assert cw.status("windows") == KNOWN
    assert calls["windows"] == 2            # stale → re-probed
    cw.invalidate()
    assert cw.status("windows") == STALE


def test_world_targeted_refresh_touches_one_section():
    cw, calls, _, _, _ = _world()
    cw.refresh()
    cw.refresh(section="monitors", force=True)   # what refresh=true means
    assert calls == {"windows": 1, "monitors": 2, "cursor": 1}


def test_world_probe_failure_is_unknown_never_fact():
    def boom():
        raise RuntimeError("no display")

    cw = ComputerWorld(clock=lambda: 1.0, probes={"windows": boom})
    cw.refresh(section="windows")
    assert cw.status("windows") == UNKNOWN
    assert cw.windows() == []               # failed read yields nothing, not fiction


def test_world_platform_error_is_unavailable():
    class PerceptionUnavailableError(Exception):
        pass

    def nope():
        raise PerceptionUnavailableError("windows only")

    cw = ComputerWorld(probes={"monitors": nope})
    cw.refresh(section="monitors")
    assert cw.status("monitors") == UNAVAILABLE


def test_world_accessors_and_snapshot_are_json_safe():
    cw, _, _, chrome, note = _world()
    cw.refresh()
    assert [w.title for w in cw.windows()] == ["Chrome - Tab", "Notepad"]
    assert cw.foreground() is chrome
    assert cw.cursor() == (123, 456)
    assert cw.primary_rect() == (0, 0, 1920, 1080)

    snap = cw.snapshot()
    json.dumps(snap)                        # must survive prompt serialization
    assert snap["status"] == {"windows": KNOWN, "monitors": KNOWN, "cursor": KNOWN}
    assert snap["foreground"]["title"] == "Chrome - Tab"
    assert snap["window_count"] == 2
    assert snap["open_windows"][0]["foreground"] is True    # hwnd match
    assert snap["open_windows"][1]["foreground"] is False
    assert snap["cursor"] == {"x": 123, "y": 456}
    assert snap["monitors"][0]["primary"] is True


def test_world_prompt_block_states_only_known_facts():
    cw, _, _, _, _ = _world()
    block = cw.prompt_block()
    assert block.startswith("[COMPUTER WORLD]")
    assert "Foreground: chrome.exe — Chrome - Tab (normal)" in block
    assert "Primary monitor: 1920x1080 at (0,0); 1 monitor(s)" in block
    assert "Cursor: (123, 456)" in block


def test_world_prompt_block_never_presents_unknown_as_fact():
    def boom():
        raise RuntimeError("gone")

    cw = ComputerWorld(probes={
        "windows": boom,
        "monitors": lambda: [MonitorInfo(0, (0, 0, 800, 600), True)],
        "cursor": lambda: (1, 2),
    })
    block = cw.prompt_block()
    assert "windows: unknown — re-check with environment_status" in block
    assert "Foreground: (nothing focused)" in block       # no invented foreground
    assert "chrome.exe" not in block


def test_find_windows_filters_by_every_token():
    cw, _, _, _, _ = _world()
    assert [w.title for w in cw.find_windows("chrome")] == ["Chrome - Tab"]
    assert [w.title for w in cw.find_windows("notepad")] == ["Notepad"]
    assert cw.find_windows("chrome notepad") == []      # both tokens required
    assert cw.find_windows("") == []


def test_set_probe_replaces_and_reseeds_section():
    cw, _, _, _, _ = _world()
    cw.refresh()
    cw.set_probe("cursor", lambda: (7, 8))
    assert cw.status("cursor") == UNKNOWN       # reseeded on swap
    assert cw.cursor() == (7, 8)                # next read runs the new probe


# ── WindowInfo schema (extended in 7B) ──────────────────────────────────────

def test_window_info_defaults_and_dict_schema():
    w = WindowInfo(title="T", process="p.exe", pid=1)
    assert w.rect is None and w.state == "unknown" and w.hwnd == 0
    payload = w.to_dict()
    assert list(payload) == ["title", "process", "pid", "rect", "state"]
    assert "hwnd" not in payload           # handle is internal, not prompt data


# ── spatial language (pure) ──────────────────────────────────────────────────

def test_anchor_point_maps_phrases_inside_rect():
    rect = (100, 200, 300, 400)
    assert anchor_point(rect, "top-left") == (108, 208)   # edges nudged inward
    assert anchor_point(rect, "bottom right") == (292, 392)
    assert anchor_point(rect, "center") == (200, 300)
    assert anchor_point(rect, "left") == (108, 300)
    assert anchor_point(rect, "top") == (200, 208)


def test_anchor_point_never_guesses():
    assert anchor_point((100, 200, 300, 400), "nowhere special") is None
    assert anchor_point((100, 200, 300, 400), "") is None
    assert anchor_point(None, "center") is None


def test_parse_spatial_detects_anchor_language():
    assert parse_spatial("click the top-left button")
    assert parse_spatial("in the center")
    assert not parse_spatial("click the blue button")
    assert not parse_spatial("")


def test_pick_window_spatial_and_ordinal_language():
    w = _win("Chrome - Tab", "chrome.exe", (0, 0, 400, 300))
    n = _win("Notepad", "notepad.exe", (500, 100, 900, 500))
    pool = [w, n]                           # z-order: w is topmost
    assert pick_window(pool, "the foreground window") is w
    assert pick_window(pool, "the window behind") is n
    assert pick_window(pool, "the window on the right") is n
    assert pick_window(pool, "the window on the left") is w
    assert pick_window(pool, "chrome on the right") is w   # narrowed by title
    assert pick_window(pool, "the second window") is n
    assert pick_window(pool, "the fourth window") is None  # out of range
    assert pick_window(pool, "") is None
    assert pick_window([], "the window on the right") is None
