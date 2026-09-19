"""Reconnect signal: raised inside the TaskGroup to force a clean reconnect."""


class ReconnectSignal(Exception):
    """Raised inside the session TaskGroup to force a clean, voluntary reconnect.

    Carries `keep_context`: True for an ordinary rebuild where the stored
    resumption handle is replayed; False when the new session must start clean.
    """

    def __init__(self, keep_context: bool = True):
        super().__init__()
        self.keep_context = keep_context


def is_reconnect_signal(exc: BaseException) -> bool:
    """True if exc is a ReconnectSignal or a BaseExceptionGroup wrapping one."""
    if isinstance(exc, ReconnectSignal):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return any(is_reconnect_signal(sub) for sub in exc.exceptions)
    return False


def keep_context_of(exc: BaseException) -> bool:
    """Read keep_context off a reconnect signal, unwrapping TaskGroup groups."""
    if isinstance(exc, ReconnectSignal):
        return getattr(exc, "keep_context", True)
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            if is_reconnect_signal(sub):
                return keep_context_of(sub)
    return True
