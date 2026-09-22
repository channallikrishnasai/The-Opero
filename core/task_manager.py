"""Thread-safe lifecycle journal for OPERO tasks.

Long-running work uses explicit state transitions so UI, logs, and future remote
clients can report real progress without guessing from console output.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class TaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    CANCELLED = "cancelled"


_TERMINAL = {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.UNCERTAIN, TaskState.CANCELLED}


@dataclass
class TaskRecord:
    task_id: str
    label: str
    kind: str = "action"
    state: TaskState = TaskState.QUEUED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    detail: str = ""
    error: str = ""
    result: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data


class TaskJournal:
    """In-memory task history with strict, observable state transitions."""

    def __init__(self, max_records: int = 200) -> None:
        self._max_records = max(10, max_records)
        self._records: dict[str, TaskRecord] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def create(self, label: str, *, kind: str = "action", metadata: dict[str, Any] | None = None) -> TaskRecord:
        task = TaskRecord(
            task_id=uuid.uuid4().hex[:12],
            label=str(label or "Untitled task")[:180],
            kind=str(kind or "action")[:60],
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._records[task.task_id] = task
            self._order.append(task.task_id)
            self._trim()
        return task

    def start(self, task_id: str, detail: str = "") -> TaskRecord | None:
        return self._transition(task_id, TaskState.RUNNING, detail=detail)

    def succeed(self, task_id: str, result: str = "") -> TaskRecord | None:
        return self._transition(task_id, TaskState.SUCCEEDED, result=result)

    def fail(self, task_id: str, error: str) -> TaskRecord | None:
        return self._transition(task_id, TaskState.FAILED, error=error)

    def uncertain(self, task_id: str, detail: str) -> TaskRecord | None:
        """Close a task whose outcome has not been independently verified."""
        return self._transition(task_id, TaskState.UNCERTAIN, detail=detail)

    def cancel(self, task_id: str, detail: str = "Cancelled by user") -> TaskRecord | None:
        return self._transition(task_id, TaskState.CANCELLED, detail=detail)

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._records.get(task_id)

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            ids = self._order[-max(1, limit):]
            return [self._records[item].public() for item in reversed(ids) if item in self._records]

    def _transition(self, task_id: str, state: TaskState, *, detail: str = "", result: str = "", error: str = "") -> TaskRecord | None:
        with self._lock:
            task = self._records.get(task_id)
            if task is None or task.state in _TERMINAL:
                return None
            task.state = state
            task.updated_at = time.time()
            if detail:
                task.detail = str(detail)[:800]
            if result:
                task.result = str(result)[:4000]
            if error:
                task.error = str(error)[:2000]
            return task

    def _trim(self) -> None:
        while len(self._order) > self._max_records:
            old_id = self._order.pop(0)
            self._records.pop(old_id, None)


journal = TaskJournal()
