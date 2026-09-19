"""Tests for core.logger — centralized logging."""
import logging
import pytest


def test_get_logger_returns_logger():
    from core.logger import get_logger
    log = get_logger("test_module")
    assert isinstance(log, logging.Logger)
    assert log.name == "test_module"


def test_get_logger_multiple_calls_same_logger():
    from core.logger import get_logger
    log1 = get_logger("same_name")
    log2 = get_logger("same_name")
    assert log1 is log2


def test_setup_logging_idempotent():
    """Calling setup_logging twice should not add duplicate handlers."""
    import core.logger as logger_mod

    # Reset _CONFIGURED so we can test idempotency
    original = logger_mod._CONFIGURED
    logger_mod._CONFIGURED = False
    root = logging.getLogger()
    initial_count = len(root.handlers)
    try:
        logger_mod.setup_logging()
        after_first = len(root.handlers)
        logger_mod.setup_logging()
        after_second = len(root.handlers)
        # Second call should not add new handlers (idempotent guard)
        assert after_second == after_first
    finally:
        logger_mod._CONFIGURED = original


def test_get_logger_does_not_crash_on_special_chars():
    """Logger names with dots and underscores should work."""
    from core.logger import get_logger

    log = get_logger("core.sub.module_test")
    assert isinstance(log, logging.Logger)
    log.info("test message with special chars: %s", "hello")
