"""Phase 7B: continuous cursor actions — pure pattern geometry and the
bounded start/modify/stop engine (interruption, caps, held-button release)."""
import sys
import time
from types import SimpleNamespace

from core.continuous import (
    MAX_DURATION, MAX_REPEAT, MAX_SIZE, PATTERNS, STEPS,
    ActionEngine, engine, pattern_points,
)


# ── geometry (pure) ──────────────────────────────────────────────────────────

def test_line_pattern_is_horizontal_and_bounded():
    pts = pattern_points("line", cx=50, cy=60, size=100, steps=4)
    assert len(pts) == 5
    assert pts[0] == (0, 60) and pts[-1] == (100, 60)
    assert all(p[1] == 60 for p in pts)


def test_circle_closes_on_itself():
    pts = pattern_points("circle", cx=0, cy=0, size=100)
    assert len(pts) == STEPS + 1
    assert abs(pts[0][0] - pts[-1][0]) <= 1
    assert abs(pts[0][1] - pts[-1][1]) <= 1


def test_square_hits_its_corners():
    pts = pattern_points("square", cx=50, cy=60, size=100, steps=48)
    corners = {(0, 10), (100, 10), (100, 110), (0, 110)}
    assert corners <= set(pts)


def test_spiral_starts_at_center():
    pts = pattern_points("spiral", cx=10, cy=20, size=100)
    assert pts[0] == (10, 20)
    assert len(pts) == STEPS * 2 + 1


def test_figure_eight_exists_and_is_symmetric_enough():
    pts = pattern_points("figure_eight", cx=0, cy=0, size=100)
    assert len(pts) == STEPS + 1
    assert pts[0] == (0, 0)                     # starts at the crossing


def test_unknown_pattern_returns_no_path():
    assert pattern_points("wiggle", 0, 0, 100) == []
    assert pattern_points("", 0, 0, 100) == []


def test_pattern_size_is_capped():
    huge = pattern_points("circle", cx=0, cy=0, size=10 ** 9)
    assert all(abs(p[0]) <= MAX_SIZE / 2 + 1 for p in huge)


# ── engine ──────────────────────────────────────────────────────────────────

def _fast_engine():
    return ActionEngine(move=lambda x, y: None, position=lambda: (10, 20),
                        sleep=lambda s: None)


def test_engine_rejects_unknown_pattern_with_candidates():
    r = _fast_engine().start({"pattern": "wiggle"})
    assert r["state"] == "failed"
    for name in PATTERNS:
        assert name in r["error"]


def test_engine_rejects_bad_parameters():
    r = _fast_engine().start({"pattern": "circle", "x": "nope"})
    assert r["state"] == "failed"
    assert "bad parameter" in r["error"]


def test_engine_caps_duration_size_and_repeat():
    eng = ActionEngine(move=lambda x, y: None, position=lambda: (0, 0),
                       sleep=lambda s: None)
    r = eng.start({"pattern": "line", "duration": 9999, "repeat": 9999,
                   "size": 10 ** 9, "x": 0, "y": 0})
    eng.stop("test")
    assert r["duration"] <= MAX_DURATION
    assert r["repeat"] <= MAX_REPEAT
    assert r["size"] <= MAX_SIZE


def test_engine_runs_to_completion_and_reports_final_position():
    eng = _fast_engine()
    r = eng.start({"pattern": "circle", "x": 0, "y": 0, "size": 40,
                   "duration": 0.2, "repeat": 1})
    assert r["state"] == "running"
    eng._thread.join(timeout=5.0)
    st = eng.status()
    assert st["state"] == "completed"
    assert st["points"] > 0
    assert st["pass_no"] == 1
    assert st["final"] == (10, 20)


def test_engine_refuses_second_run_while_running():
    eng = ActionEngine(move=lambda x, y: None, position=lambda: (0, 0),
                       sleep=lambda s: time.sleep(0.002))
    eng.start({"pattern": "circle", "x": 0, "y": 0, "duration": 60,
               "repeat": 100})
    try:
        again = eng.start({"pattern": "line", "x": 0, "y": 0})
        assert again["state"] == "already_running"
        assert "stop it first" in again["error"]
    finally:
        eng.stop("test")


def test_engine_modify_retunes_live_and_refuses_when_idle():
    idle = _fast_engine()
    r = idle.modify({"speed": 2.0})
    assert r["state"] == "idle" and "nothing is running" in r["error"]

    eng = ActionEngine(move=lambda x, y: None, position=lambda: (0, 0),
                       sleep=lambda s: time.sleep(0.002))
    eng.start({"pattern": "circle", "x": 0, "y": 0, "duration": 60,
               "repeat": 100})
    try:
        r = eng.modify({"speed": 2.0, "scale": 3.0, "repeat": 7})
        assert r["state"] == "modified"
        assert r["speed"] == 2.0 and r["scale"] == 3.0 and r["repeat"] == 7
        r = eng.modify({"speed": 99})            # capped, not accepted raw
        assert r["speed"] <= 10.0
    finally:
        eng.stop("test")


def test_engine_stop_interrupts_and_records_reason():
    eng = ActionEngine(move=lambda x, y: None, position=lambda: (0, 0),
                       sleep=lambda s: time.sleep(0.002))
    eng.start({"pattern": "line", "x": 0, "y": 0, "duration": 60,
               "repeat": 100})
    out = eng.stop(reason="interrupt")
    assert out["state"] == "stopped"
    assert out["reason"] == "interrupt"
    st = eng.status()
    assert st["state"] == "stopped"
    assert not eng._thread.is_alive()           # loop actually exited


def test_engine_stop_without_run_returns_last_state():
    eng = _fast_engine()
    assert eng.stop() == {"state": "idle"}


def test_engine_loop_fails_truthfully_when_move_raises(monkeypatch):
    def boom(x, y):
        raise RuntimeError("display lost")

    eng = ActionEngine(move=boom, position=lambda: (0, 0), sleep=lambda s: None)
    eng.start({"pattern": "line", "x": 0, "y": 0, "duration": 0.2})
    eng._thread.join(timeout=5.0)
    st = eng.status()
    assert st["state"] == "failed"
    assert "display lost" in st["error"]


def test_engine_releases_held_button_even_on_stop(monkeypatch):
    held = {"down": [], "up": []}
    fake = SimpleNamespace(
        mouseDown=lambda button="left": held["down"].append(button),
        mouseUp=lambda button="left": held["up"].append(button),
        moveTo=lambda *a, **k: None,
    )
    monkeypatch.setitem(sys.modules, "pyautogui", fake)

    eng = ActionEngine(move=lambda x, y: None, position=lambda: (0, 0),
                       sleep=lambda s: time.sleep(0.002))
    eng.start({"pattern": "line", "x": 0, "y": 0, "duration": 60,
               "repeat": 100, "button": "right"})
    try:
        eng.stop("interrupt")
    finally:
        pass
    assert held["down"] == ["right"]
    assert held["up"] == ["right"]              # released on the way out


def test_engine_singleton_is_shared():
    assert engine() is engine()
