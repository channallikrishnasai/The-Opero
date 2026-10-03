"""Phase 7A: tool & environment intelligence regressions —
open_app reuse/verification, file find ranking + task-folder scope,
whatsapp dependency guard, wallpaper failure path, tool-contract pins."""
import platform
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.context as cc


@pytest.fixture(autouse=True)
def fresh_task_ctx(monkeypatch):
    """Isolate every test from (and avoid polluting) the process singleton."""
    tc = cc.TaskContext()
    monkeypatch.setattr(cc, "_TASK", tc)
    return tc


# ── open_app: reuse, alias fix, honest verification ──────────────────────────

def test_token_contains_whole_word_aliases():
    from actions.open_app import _token_contains
    assert _token_contains("open microsoft word", "word")
    assert not _token_contains("wordpad", "word")      # old substring bug
    assert not _token_contains("code", "visual studio code")
    assert _token_contains("visual studio code editor", "visual studio code")


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows aliases")
def test_normalize_word_not_wordpad():
    from actions import open_app as oa
    assert oa._normalize("word") == "winword"
    assert oa._normalize("wordpad") == "wordpad"
    assert oa._normalize("Chrome") == "chrome"


def test_reuse_focuses_existing_window_verified(monkeypatch):
    from actions import open_app as oa
    monkeypatch.setattr(oa, "_is_running", lambda app: True)
    monkeypatch.setattr(oa, "_focus_existing", lambda app: ("Chrome - Tab", True))
    msg = oa.open_app({"app_name": "chrome"})
    assert "already open" in msg
    assert "verified in front" in msg


def test_reuse_focus_wording_when_foreground_unreadable(monkeypatch):
    from actions import open_app as oa
    monkeypatch.setattr(oa, "_is_running", lambda app: True)
    monkeypatch.setattr(oa, "_focus_existing", lambda app: ("Chrome - Tab", None))
    msg = oa.open_app({"app_name": "chrome"})
    assert "already open" in msg
    assert "could not be re-read" in msg


def test_launch_reports_verified_when_process_observed(monkeypatch):
    from actions import open_app as oa
    monkeypatch.setattr(oa, "_is_running", lambda app: False)
    monkeypatch.setitem(oa._OS_LAUNCHERS, "Windows", lambda app: True)
    monkeypatch.setattr(oa, "_verify_launch", lambda app, was_running: True)
    msg = oa.open_app({"app_name": "notepad"})
    assert "verified: it is now running" in msg


def test_launch_reports_could_not_verify(monkeypatch):
    from actions import open_app as oa
    monkeypatch.setattr(oa, "_is_running", lambda app: False)
    monkeypatch.setitem(oa._OS_LAUNCHERS, "Windows", lambda app: True)
    monkeypatch.setattr(oa, "_verify_launch", lambda app, was_running: False)
    msg = oa.open_app({"app_name": "notepad"})
    assert "could NOT verify" in msg


def test_launch_reports_unverifiable_when_psutil_missing(monkeypatch):
    from actions import open_app as oa
    monkeypatch.setattr(oa, "_is_running", lambda app: False)
    monkeypatch.setitem(oa._OS_LAUNCHERS, "Windows", lambda app: True)
    monkeypatch.setattr(oa, "_verify_launch", lambda app, was_running: None)
    msg = oa.open_app({"app_name": "notepad"})
    assert "cannot verify it is running" in msg


def test_new_window_forces_launch_even_when_running(monkeypatch):
    from actions import open_app as oa
    monkeypatch.setattr(oa, "_is_running", lambda app: True)
    monkeypatch.setattr(oa, "_focus_existing",
                        lambda app: pytest.fail("focus must not run with new_window"))
    monkeypatch.setitem(oa._OS_LAUNCHERS, "Windows", lambda app: True)
    monkeypatch.setattr(oa, "_verify_launch", lambda app, was_running: True)
    msg = oa.open_app({"app_name": "chrome", "new_window": True})
    assert "verified: its process is running" in msg


def test_verify_launch_false_after_timeout(monkeypatch):
    from actions import open_app as oa
    monkeypatch.setattr(oa, "_is_running", lambda app: False)
    assert oa._verify_launch("ghost-app", was_running=False, timeout=0.05) is False


def test_verify_launch_cannot_verify_without_psutil(monkeypatch):
    from actions import open_app as oa
    monkeypatch.setattr(oa, "_PSUTIL", None)
    assert oa._verify_launch("anything", was_running=False) is None


def test_open_app_tool_declares_reuse_contract():
    from actions.open_app import TOOL
    assert "new_window" in TOOL["parameters"]["properties"]
    assert "already open" in TOOL["description"]


# ── file_controller: ranking + context-aware scope ───────────────────────────

def test_rank_matches_best_first_deterministic():
    from actions.file_controller import rank_matches
    items = [
        SimpleNamespace(name="zreport_extra.pdf"),
        SimpleNamespace(name="notes.txt"),
        SimpleNamespace(name="report draft.pdf"),
        SimpleNamespace(name="report.pdf"),
    ]
    ordered = [p.name for p in rank_matches("report", items)]
    # prefix tier first (stable input order), then substring, then the rest
    assert ordered[:2] == ["report draft.pdf", "report.pdf"]
    assert ordered[2] == "zreport_extra.pdf"
    assert ordered[3] == "notes.txt"


def test_rank_matches_exact_filename_wins():
    from actions.file_controller import rank_matches
    items = [
        SimpleNamespace(name="xreport.pdf"),
        SimpleNamespace(name="report.pdf"),
        SimpleNamespace(name="notes.txt"),
    ]
    ordered = [p.name for p in rank_matches("report.pdf", items)]
    assert ordered[0] == "report.pdf"


def test_find_orders_best_match_first(tmp_path):
    from actions import file_controller as fc
    (tmp_path / "xreport.pdf").write_text("x", encoding="utf-8")
    (tmp_path / "report.pdf").write_text("r", encoding="utf-8")
    out = fc.find_files(name="report.pdf", path=str(tmp_path))
    lines = out.splitlines()
    assert "Found" in lines[0]
    assert "report.pdf (" in lines[1]           # exact match listed first
    assert "xreport.pdf" in lines[2]


def test_find_uses_task_folder_when_path_omitted(fresh_task_ctx, tmp_path):
    from actions import file_controller as fc
    (tmp_path / "the-file.txt").write_text("hi", encoding="utf-8")
    fresh_task_ctx.note_folder(str(tmp_path))
    out = fc.file_controller({"action": "find", "name": "the-file"})
    assert "the-file.txt" in out
    assert "Access denied" not in out


def test_list_files_updates_current_folder(fresh_task_ctx, tmp_path):
    from actions import file_controller as fc
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    fc.list_files(str(tmp_path))
    assert fresh_task_ctx.current_folder == str(tmp_path)


def test_read_file_notes_verified_resource(fresh_task_ctx, tmp_path):
    from actions import file_controller as fc
    target = tmp_path / "doc.txt"
    target.write_text("hello", encoding="utf-8")
    fc.read_file(str(tmp_path), name="doc.txt")
    cur = fresh_task_ctx.current_resource()
    assert cur is not None
    assert cur["label"] == "doc.txt"
    assert cur["verified"] is True


def test_file_controller_tool_declares_new_params():
    from actions.file_controller import TOOL
    props = TOOL["parameters"]["properties"]
    assert "folder" in props
    assert "max_results" in props


# ── whatsapp bridge dependency guard ─────────────────────────────────────────

def test_whatsapp_deps_guard(tmp_path, monkeypatch):
    import whatsapp_call as w
    monkeypatch.setattr(w, "BRIDGE_DIR", tmp_path)
    assert w._bridge_deps_present() is False
    (tmp_path / "node_modules" / "whatsapp-web.js").mkdir(parents=True)
    assert w._bridge_deps_present() is True


# ── desktop wallpaper: honest failure for missing input ──────────────────────

def test_wallpaper_missing_image_reports_not_found():
    from actions.desktop import set_wallpaper
    msg = set_wallpaper(str(Path(__file__).parent / "does_not_exist.png"))
    assert "not found" in msg.lower()


# ── contract pins (text-level) ───────────────────────────────────────────────

def test_browser_control_declares_scope_and_url():
    from actions.browser_control import TOOL
    assert "separately-managed" in TOOL["description"]
    assert "url" in TOOL["parameters"]["properties"]


def test_main_declares_environment_status_and_fixed_manage_monitor():
    root = Path(__file__).resolve().parents[1]
    text = (root / "main.py").read_text(encoding="utf-8")
    assert '"name": "environment_status"' in text
    assert '"name": "manage_monitor"' in text
    assert "does NOT track news" in text        # old fake news-topic semantics gone
    assert "dispatch_monitor" in text           # handler routes through dispatch()
