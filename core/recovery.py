"""Auditable recovery primitives for managed OPERO source changes.

This module intentionally does not generate or apply AI patches. It provides the
safe mechanics needed by a review-first self-heal workflow: backup, validation,
atomic replace, and rollback.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RECOVERY_DIR = BASE_DIR / "config" / "recovery"
BACKUP_DIR = RECOVERY_DIR / "backups"
HISTORY_FILE = RECOVERY_DIR / "history.json"


@dataclass
class RecoveryRecord:
    change_id: str
    target: str
    backup: str
    created_at: float
    status: str
    reason: str


def validate_python(source: str, filename: str = "<staged>") -> str | None:
    """Return an error string when staged Python is invalid, otherwise None."""
    try:
        ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return f"Syntax error on line {exc.lineno}: {exc.msg}"
    return None


def apply_reviewed_text(target: Path, replacement: str, *, reason: str) -> RecoveryRecord:
    """Backup and atomically replace a first-party text file after validation.

    The caller must obtain human approval before invoking this method. Python
    files are parsed before disk changes; any failure preserves the original.
    """
    resolved = target.resolve()
    try:
        resolved.relative_to(BASE_DIR.resolve())
    except ValueError as exc:
        raise ValueError("Recovery changes must stay inside the OPERO project.") from exc
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    if resolved.suffix == ".py":
        error = validate_python(replacement, resolved.name)
        if error:
            raise ValueError(error)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    change_id = uuid.uuid4().hex[:12]
    backup = BACKUP_DIR / f"{resolved.name}.{change_id}.bak"
    shutil.copy2(resolved, backup)
    tmp = resolved.with_name(f".{resolved.name}.{change_id}.tmp")
    try:
        tmp.write_text(replacement, encoding="utf-8")
        os.replace(tmp, resolved)
    except Exception:
        tmp.unlink(missing_ok=True)
        shutil.copy2(backup, resolved)
        raise

    record = RecoveryRecord(change_id, str(resolved), str(backup), time.time(), "applied", str(reason)[:500])
    _append(record)
    return record


def rollback(change_id: str = "latest") -> RecoveryRecord | None:
    records = _load()
    for record in reversed(records):
        if record.status == "applied" and (change_id == "latest" or record.change_id == change_id):
            target, backup = Path(record.target), Path(record.backup)
            if not target.exists() or not backup.is_file():
                raise FileNotFoundError("Recovery target or backup is unavailable.")
            shutil.copy2(backup, target)
            record.status = "rolled_back"
            _save(records)
            return record
    return None


def history(limit: int = 20) -> list[RecoveryRecord]:
    return list(reversed(_load()[-max(1, limit):]))


def _load() -> list[RecoveryRecord]:
    if not HISTORY_FILE.is_file():
        return []
    try:
        return [RecoveryRecord(**item) for item in json.loads(HISTORY_FILE.read_text(encoding="utf-8"))]
    except (OSError, ValueError, TypeError):
        return []


def _append(record: RecoveryRecord) -> None:
    records = _load()
    records.append(record)
    _save(records)


def _save(records: list[RecoveryRecord]) -> None:
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps([asdict(item) for item in records], indent=2), encoding="utf-8")
