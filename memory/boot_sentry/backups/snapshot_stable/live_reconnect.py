"""Pure helpers for classifying Gemini Live transport shutdowns."""
from __future__ import annotations


def is_clean_live_close(exc: BaseException) -> bool:
    """Return True for a normal websocket 1000 close, including task groups."""
    if isinstance(exc, BaseExceptionGroup):
        return any(is_clean_live_close(sub) for sub in exc.exceptions)
    message = str(exc).lower()
    return "connectionclosedok" in message or message.startswith("1000 ") or " 1000 (ok)" in message
