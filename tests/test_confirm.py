"""Tests for core.confirm — human confirmation gate."""
import time
import threading
import pytest


def test_request_without_bind_returns_no_interface_msg():
    """Before bind() is called, request() returns a refusal message."""
    import core.confirm as confirm

    # Ensure no callbacks are bound
    original_show = confirm._show_cb
    original_hide = confirm._hide_cb
    confirm._show_cb = None
    confirm._hide_cb = None
    try:
        result = confirm.request("test", "Shutdown", "Are you sure?", lambda: "done")
        assert "not available" in result.lower() or "cannot confirm" in result.lower()
    finally:
        confirm._show_cb = original_show
        confirm._hide_cb = original_hide


def test_request_with_bind_calls_show():
    """After bind(), request() invokes the show callback and returns a pending message."""
    import core.confirm as confirm

    original_show = confirm._show_cb
    original_hide = confirm._hide_cb
    shown = []

    def mock_show(title, detail):
        shown.append((title, detail))

    confirm._show_cb = mock_show
    confirm._hide_cb = lambda: None
    try:
        result = confirm.request("k1", "Shutdown", "Are you sure?", lambda: "done")
        assert len(shown) == 1
        assert shown[0][0] == "Shutdown"
        assert "CONFIRMATION_PENDING" in result
    finally:
        confirm._show_cb = original_show
        confirm._hide_cb = original_hide
        confirm._pending = None


def test_pending_title_returns_empty_when_nothing_pending():
    """pending_title() returns '' when there is no pending confirmation."""
    import core.confirm as confirm

    original_pending = confirm._pending
    confirm._pending = None
    try:
        assert confirm.pending_title() == ""
    finally:
        confirm._pending = original_pending


def test_resolve_cancelled():
    """resolve(accepted=False) clears pending and does not run the action."""
    import core.confirm as confirm

    original_show = confirm._show_cb
    original_hide = confirm._hide_cb
    original_pending = confirm._pending
    ran = []

    confirm._show_cb = lambda t, d: None
    confirm._hide_cb = lambda: None
    try:
        confirm.request("k1", "Test", "detail", lambda: ran.append("ran") or "ok")
        assert confirm.pending_title() == "Test"
        confirm.resolve(accepted=False)
        time.sleep(0.1)
        assert ran == []
        assert confirm.pending_title() == ""
    finally:
        confirm._show_cb = original_show
        confirm._hide_cb = original_hide
        confirm._pending = original_pending


def test_resolve_confirmed_runs_action():
    """resolve(accepted=True) runs the stored callable in a worker thread."""
    import core.confirm as confirm

    original_show = confirm._show_cb
    original_hide = confirm._hide_cb
    original_pending = confirm._pending
    ran = []
    lock = threading.Lock()

    def mock_action():
        with lock:
            ran.append("executed")
        return "ok"

    confirm._show_cb = lambda t, d: None
    confirm._hide_cb = lambda: None
    try:
        confirm.request("k1", "Test", "detail", mock_action)
        confirm.resolve(accepted=True)
        time.sleep(0.3)
        with lock:
            assert "executed" in ran
    finally:
        confirm._show_cb = original_show
        confirm._hide_cb = original_hide
        confirm._pending = original_pending


def test_resolve_no_pending():
    """resolve() when nothing is pending does not raise."""
    import core.confirm as confirm

    original_show = confirm._show_cb
    original_hide = confirm._hide_cb
    original_pending = confirm._pending
    confirm._show_cb = lambda t, d: None
    confirm._hide_cb = lambda: None
    confirm._pending = None
    try:
        confirm.resolve(accepted=True)
    finally:
        confirm._show_cb = original_show
        confirm._hide_cb = original_hide
        confirm._pending = original_pending
