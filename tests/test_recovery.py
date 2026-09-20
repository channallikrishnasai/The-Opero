from pathlib import Path

import pytest

from core import recovery


def test_apply_and_rollback_reviewed_python(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(recovery, "BASE_DIR", tmp_path)
    monkeypatch.setattr(recovery, "RECOVERY_DIR", tmp_path / "recovery")
    monkeypatch.setattr(recovery, "BACKUP_DIR", tmp_path / "recovery" / "backups")
    monkeypatch.setattr(recovery, "HISTORY_FILE", tmp_path / "recovery" / "history.json")
    target = tmp_path / "sample.py"
    target.write_text("value = 1\n", encoding="utf-8")
    record = recovery.apply_reviewed_text(target, "value = 2\n", reason="test")
    assert target.read_text(encoding="utf-8") == "value = 2\n"
    rolled = recovery.rollback(record.change_id)
    assert rolled is not None
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_invalid_python_never_replaces_target(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(recovery, "BASE_DIR", tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("value = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Syntax error"):
        recovery.apply_reviewed_text(target, "def broken(:\n", reason="test")
    assert target.read_text(encoding="utf-8") == "value = 1\n"
