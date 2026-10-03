"""Phase 7A: manage_monitor tool contract.

Regression core: the old handler called add_monitor(topic) against a signature
of (monitor_type, target, threshold, ...) — every 'add' died with a TypeError.
`dispatch` must never raise on model-facing input and must guide instead.
"""
import pytest

from actions import background_monitor as bm


@pytest.fixture(autouse=True)
def clean_monitors():
    with bm._monitor_lock:
        bm._monitors.clear()
    yield
    with bm._monitor_lock:
        bm._monitors.clear()


def _stored():
    with bm._monitor_lock:
        return dict(bm._monitors)


def test_add_system_monitor_never_raises_typeerror():
    msg = bm.dispatch({"action": "add", "type": "system",
                       "target": "cpu", "threshold": 90})
    assert isinstance(msg, str)
    assert msg.startswith("Started monitoring system (cpu)")
    assert "cpu" in bm.get_monitors()


def test_add_accepts_legacy_topic_field():
    msg = bm.dispatch({"action": "add", "type": "system",
                       "topic": "ram", "threshold": 80})
    assert "Started monitoring" in msg


def test_add_rejects_unknown_type_with_guidance():
    msg = bm.dispatch({"action": "add", "type": "news",
                       "target": "ai", "threshold": 1})
    assert "system|crypto|website" in msg


def test_system_monitor_only_cpu_or_ram():
    msg = bm.dispatch({"action": "add", "type": "system",
                       "target": "disk", "threshold": 90})
    assert "cpu" in msg and "ram" in msg


def test_website_monitor_requires_full_url():
    msg = bm.dispatch({"action": "add", "type": "website",
                       "target": "example.com", "threshold": 500})
    assert "http" in msg


def test_non_numeric_threshold_rejected():
    msg = bm.dispatch({"action": "add", "type": "system",
                       "target": "cpu", "threshold": "high"})
    assert "numeric" in msg


def test_interval_clamped_to_sane_bounds():
    bm.dispatch({"action": "add", "type": "system", "target": "cpu",
                 "threshold": 90, "interval": 1})
    entries = _stored().values()
    assert all(e["interval"] == 10 for e in entries)   # floor of 10s


def test_invalid_action_and_missing_target_guidance():
    assert bm.dispatch({"action": "watch"}) == "Specify action (add/remove/list)."
    assert "target" in bm.dispatch({"action": "remove"})


def test_list_empty_and_remove_missing():
    assert bm.dispatch({"action": "list"}) == "No topics are being monitored."
    assert "No monitor found" in bm.dispatch({"action": "remove", "target": "cpu"})


def test_add_remove_roundtrip():
    bm.dispatch({"action": "add", "type": "system",
                 "target": "cpu", "threshold": 95})
    assert "Removed monitor" in bm.dispatch({"action": "remove", "target": "cpu"})
    assert bm.dispatch({"action": "list"}) == "No topics are being monitored."
