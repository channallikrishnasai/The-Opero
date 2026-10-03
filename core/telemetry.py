"""Bounded in-memory execution telemetry (Phase 7A).

Engineering measurement only: a ring buffer of timing records that tests and
debugging sessions can read. No external service, no persistence, no invented
baselines — the window is exactly `_MAX` records, so `count()` is a windowed
count, not a lifetime total.
"""

import threading
import time
from collections import deque

_MAX = 256

_records: deque[dict] = deque(maxlen=_MAX)
_lock = threading.Lock()


def record(event: str, ms: float, **fields) -> dict:
    """Append one timing record: event name, duration in ms, extra fields."""
    rec: dict = {"event": str(event), "ms": round(float(ms), 3), "ts": time.time()}
    rec.update(fields)
    with _lock:
        _records.append(rec)
    return rec


def recent(limit: int = 20) -> list[dict]:
    """The newest `limit` records, oldest first."""
    n = max(0, int(limit))
    with _lock:
        return list(_records)[-n:] if n else []


def count(event: str | None = None) -> int:
    """Windowed record count, optionally filtered by event name."""
    with _lock:
        if event is None:
            return len(_records)
        return sum(1 for r in _records if r["event"] == event)


def reset() -> None:
    """Clear the buffer (tests)."""
    with _lock:
        _records.clear()
