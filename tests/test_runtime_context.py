"""Phase 7A: core.context and core.telemetry — environment snapshot,
current-task context, utterance freshness, bounded telemetry."""
from types import SimpleNamespace

from core.context import (
    EnvironmentSnapshot,
    TaskContext,
    current_utterance,
    env_cache,
    summarize_args,
    task_ctx,
    verdict,
)
from core import telemetry


def _fake_ctx(active_title="Notepad", window_titles=("Notepad - untitled",)):
    windows = [SimpleNamespace(title=t, process="notepad.exe") for t in window_titles]
    return SimpleNamespace(
        timestamp=123.0,
        active_window=(
            SimpleNamespace(title=active_title, process="notepad.exe")
            if active_title else None
        ),
        windows=windows,
        browser=SimpleNamespace(detected=False),
    )


# ── EnvironmentSnapshot ──────────────────────────────────────────────────────

def test_env_snapshot_caches_within_ttl_and_force_refreshes():
    calls = []
    snap = EnvironmentSnapshot(
        ttl=100.0, clock=lambda: 10.0,
        probe=lambda: (calls.append(1), _fake_ctx())[1],
    )
    snap.get()
    snap.get()
    assert len(calls) == 1          # cached inside the TTL
    snap.get(force=True)
    assert len(calls) == 2          # forced rebuild


def test_env_snapshot_invalidate_triggers_targeted_refresh():
    calls = []
    snap = EnvironmentSnapshot(
        ttl=100.0, clock=lambda: 10.0,
        probe=lambda: (calls.append(1), _fake_ctx())[1],
    )
    snap.get()
    snap.invalidate()
    snap.get()
    assert len(calls) == 2          # every tool dispatch invalidates → rebuild


def test_env_snapshot_probe_failure_degrades_truthfully():
    def boom():
        raise RuntimeError("no session")

    snap = EnvironmentSnapshot(probe=boom)
    data = snap.get()
    assert "error" in data
    block = snap.prompt_block()
    assert block.startswith("[CURRENT ENVIRONMENT]")
    assert "unavailable" in block


def test_env_snapshot_prompt_block_content():
    snap = EnvironmentSnapshot(probe=lambda: _fake_ctx())
    block = snap.prompt_block()
    assert "Foreground: notepad.exe — Notepad" in block
    assert "Open windows (1): Notepad - untitled" in block
    assert "environment_status" in block      # re-check instruction present


def test_env_snapshot_caps_window_list():
    titles = tuple(f"Window {i}" for i in range(20))
    snap = EnvironmentSnapshot(probe=lambda: _fake_ctx(window_titles=titles))
    data = snap.get()
    assert data["window_count"] == 20
    assert len(data["open_windows"]) == 12    # MAX_WINDOWS


def test_env_cache_is_singleton():
    assert env_cache() is env_cache()
    assert task_ctx() is task_ctx()


# ── TaskContext ──────────────────────────────────────────────────────────────

def test_resource_renoting_moves_to_front_without_duplicate():
    tc = TaskContext(clock=lambda: 100.0)
    tc.note_resource("file", "C:/x/a.txt", label="a.txt")
    tc.note_resource("file", "C:/x/b.txt", label="b.txt")
    tc.note_resource("file", "C:/x/a.txt", label="a.txt", verified=True)
    labels = [r["label"] for r in tc.recent_resources(50)]
    assert labels == ["b.txt", "a.txt"]       # a.txt refreshed, not duplicated
    assert tc.current_resource()["verified"] is True


def test_resource_capacity_is_bounded():
    tc = TaskContext()
    for i in range(10):
        tc.note_resource("file", f"/f{i}")
    assert len(tc.recent_resources(50)) == 8  # MAX_RESOURCES
    assert tc.current_resource()["id"] == "/f9"


def test_actions_capacity_is_bounded():
    tc = TaskContext()
    for i in range(20):
        tc.note_action("tool", f"t{i}")
    assert len(tc.recent_actions(50)) == 12   # MAX_ACTIONS


def test_resolve_pronouns_and_kind_words():
    tc = TaskContext()
    tc.note_resource("file", "/one.txt", label="one.txt")
    tc.note_resource("application", "Chrome", label="Chrome")
    assert tc.resolve("open it")["label"] == "Chrome"          # current
    assert tc.resolve("that file")["label"] == "one.txt"       # kind filter
    assert tc.resolve("the previous one")["label"] == "one.txt"  # previous
    assert tc.resolve("") is None


def test_prompt_block_empty_when_nothing_known():
    assert TaskContext().prompt_block() == ""


def test_prompt_block_reports_folder_resource_and_action_outcomes():
    tc = TaskContext(clock=lambda: 1000.0)
    tc.note_folder("C:/dl")
    tc.note_action("find", "report.pdf", outcome="done")
    tc.note_resource("file", "C:/dl/report.pdf", label="report.pdf", verified=True)
    block = tc.prompt_block()
    assert block.startswith("[CURRENT TASK CONTEXT]")
    assert "Current folder: C:/dl" in block
    assert "report.pdf (verified" in block
    assert "find report.pdf → done" in block


# ── helpers ──────────────────────────────────────────────────────────────────

def test_current_utterance_prefers_live_voice_buffer():
    assert current_utterance("show an apple", ["User: stale"]) == "show an apple"
    assert current_utterance("", ["User: typed one"]) == "typed one"
    assert current_utterance("  ", ["no user line"]) == ""


def test_verdict_classification():
    assert verdict("[CONFIRMATION_PENDING] waiting") == "pending"
    assert verdict("Failed to open the app") == "failed"
    assert verdict("There were no errors in the build") == "done"  # "no error" guard
    assert verdict("Opened successfully") == "done"


def test_summarize_args_targets_only_and_capped():
    assert summarize_args({"query": "hello", "url": None, "path": ""}) == "query=hello"
    assert summarize_args("nope") == ""
    long = summarize_args({k: "v" * 100 for k in ("query", "url")})
    assert len(long) <= 160


# ── telemetry ────────────────────────────────────────────────────────────────

def test_telemetry_ring_buffer_is_bounded():
    telemetry.reset()
    for i in range(300):
        telemetry.record("evt", i)
    assert telemetry.count() == 256
    assert telemetry.count("evt") == 256
    newest = telemetry.recent(5)
    assert len(newest) == 5
    assert newest[-1]["ms"] == 299.0
    telemetry.reset()
    assert telemetry.count() == 0


def test_telemetry_record_shape():
    telemetry.reset()
    rec = telemetry.record("tool", 1.5, ok=True)
    assert rec["event"] == "tool"
    assert rec["ms"] == 1.5
    assert rec["ok"] is True
    assert "ts" in rec
    telemetry.reset()
