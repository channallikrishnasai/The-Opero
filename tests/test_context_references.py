"""Phase 7B: contextual references — ordinals against the LAST result set,
user corrections, result noting, and file-search recency ranking."""
import json
from types import SimpleNamespace

from core.context import MAX_RESULTS, TaskContext, task_ctx
from actions.file_controller import rank_matches


# ── noting results ───────────────────────────────────────────────────────────

def test_note_results_replaces_previous_set():
    tc = TaskContext()
    tc.note_results("file", ["a.txt", "b.txt", "c.txt"])
    tc.note_results("tab", ["Docs", "Mail"])
    assert tc.summary()["last_results"] == ["Docs", "Mail"]   # latest wins


def test_note_results_caps_and_extracts_labels():
    tc = TaskContext()
    tc.note_results("file", [f"f{i}.txt" for i in range(20)])
    assert len(tc.summary()["last_results"]) == MAX_RESULTS
    tc.note_results("file", [{"title": "Page A"}, {"path": "/tmp/x"}, "", None])
    assert tc.summary()["last_results"] == ["Page A", "/tmp/x"]


# ── ordinal resolution ───────────────────────────────────────────────────────

def test_ordinals_resolve_against_last_results_in_order():
    tc = TaskContext(clock=lambda: 100.0)
    tc.note_results("file", ["alpha.txt", "beta.txt", "gamma.txt"])
    assert tc.resolve("the second result")["id"] == "beta.txt"
    assert tc.resolve("first result")["id"] == "alpha.txt"
    assert tc.resolve("third result")["id"] == "gamma.txt"
    assert tc.resolve("last result")["id"] == "gamma.txt"


def test_ordinal_labels_are_positional_and_unverified():
    tc = TaskContext(clock=lambda: 100.0)
    tc.note_results("file", ["alpha.txt", "beta.txt"])
    rec = tc.resolve("the second result")
    assert rec["label"] == "result 2: beta.txt"
    assert rec["verified"] is False


def test_ordinal_out_of_range_or_absent_returns_none():
    tc = TaskContext()
    tc.note_results("file", ["a.txt", "b.txt"])
    assert tc.resolve("the fifth result") is None
    assert tc.resolve("the first tab") is None       # kind mismatch → no guess
    fresh = TaskContext()
    assert fresh.resolve("the second result") is None  # no results at all


def test_plain_references_use_current_and_previous_resources():
    tc = TaskContext(clock=lambda: 100.0)
    tc.note_resource("file", "one.txt", "one.txt")
    tc.note_resource("file", "two.txt", "two.txt")
    assert tc.resolve("it")["label"] == "two.txt"
    assert tc.resolve("the file")["label"] == "two.txt"
    assert tc.resolve("the previous one")["label"] == "one.txt"


# ── corrections ──────────────────────────────────────────────────────────────

def test_correction_replaces_the_current_resource():
    tc = TaskContext(clock=lambda: 100.0)
    tc.note_resource("file", "screenshot.png", "screenshot.png")
    rec = tc.correct_resource("report.pdf", kind="file")
    assert rec["label"] == "report.pdf"
    assert rec["corrected"] is True
    cur = tc.current_resource()
    assert cur["label"] == "report.pdf"
    assert "screenshot.png" not in [r["label"] for r in tc.recent_resources()]
    assert tc.summary()["corrections"] == 1


def test_correction_with_empty_label_does_not_count():
    tc = TaskContext()
    tc.note_resource("file", "keep.txt", "keep.txt")
    tc.correct_resource("   ")
    assert tc.summary()["corrections"] == 0


def test_correction_is_visible_in_the_prompt_block():
    tc = TaskContext(clock=lambda: 100.0)
    tc.note_resource("file", "wrong.png", "wrong.png")
    tc.correct_resource("right.pdf", kind="file")
    block = tc.prompt_block()
    assert "context_note (correct=...)" in block
    assert "Current resource: file right.pdf" in block


def test_summary_stays_json_safe_with_results():
    tc = TaskContext(clock=lambda: 100.0)
    tc.note_results("file", ["a", "b"])
    tc.note_resource("file", "a", "a")
    json.dumps(tc.summary())


# ── file ranking: tier first, recency within tier ────────────────────────────

class _F:
    """Minimal file stand-in with a controllable mtime."""
    def __init__(self, name, mtime):
        self.name = name
        self._mtime = mtime

    def stat(self):
        return SimpleNamespace(st_mtime=self._mtime)


def test_rank_matches_prefers_prefix_over_substring_over_extension_only():
    items = [_F("notes.md", 1), _F("my_report_draft.docx", 1),
             _F("report_final.pdf", 1), _F("report.txt", 1)]
    ranked = [f.name for f in rank_matches("report", items)]
    assert ranked == ["report_final.pdf", "report.txt",   # prefix tier
                      "my_report_draft.docx",              # substring tier
                      "notes.md"]                          # no match at all


def test_rank_matches_exact_filename_beats_a_newer_prefix_match():
    items = [_F("report.txt", 999.0), _F("report", 1.0)]
    assert [f.name for f in rank_matches("report", items)] == ["report", "report.txt"]


def test_rank_matches_recency_breaks_ties_within_a_tier():
    items = [_F("report_old.pdf", 100.0), _F("report_new.pdf", 900.0),
             _F("report_mid.pdf", 500.0)]
    ranked = [f.name for f in rank_matches("report", items)]
    assert ranked == ["report_new.pdf", "report_mid.pdf", "report_old.pdf"]


def test_rank_matches_without_name_is_pure_recency():
    items = [_F("old.txt", 100.0), _F("new.txt", 900.0)]
    ranked = [f.name for f in rank_matches("", items)]
    assert ranked == ["new.txt", "old.txt"]


def test_rank_matches_missing_stat_falls_back_to_stable_order():
    class NoStat:
        def __init__(self, name):
            self.name = name

    items = [NoStat("b.txt"), NoStat("a.txt")]
    ranked = [f.name for f in rank_matches("", items)]
    assert ranked == ["b.txt", "a.txt"]       # equal keys keep input order


# ── find_files notes its results for ordinal follow-ups ──────────────────────

def test_find_files_notes_results_for_ordinals(tmp_path):
    (tmp_path / "alpha.txt").write_text("a")
    (tmp_path / "beta.txt").write_text("b")
    tc = task_ctx()
    old = tc.summary()["last_results"]
    try:
        from actions.file_controller import find_files
        out = find_files(name="txt", path=str(tmp_path))
        assert "alpha.txt" in out and "beta.txt" in out
        assert set(tc.summary()["last_results"]) == {"alpha.txt", "beta.txt"}
        assert tc.resolve("the first result")["id"] in ("alpha.txt", "beta.txt")
    finally:
        tc.note_results("file", old)               # leave the singleton clean
