"""Centralized logging configuration for Opero.

Usage in any module:
    from core.logger import get_logger
    log = get_logger(__name__)
    log.info("Something happened")
    log.error("Something failed", exc_info=True)
"""
import logging
import sys
import os
from pathlib import Path

_CONFIGURED = False

def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger once. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    log_dir = Path(os.environ.get("OPERO_LOG_DIR", Path(__file__).resolve().parent.parent / "logs"))
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "opero.log"

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler — compact format
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname).1s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(ch)

    # File handler — detailed format, 5 MB rotation
    try:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(str(log_file), maxBytes=5_000_000, backupCount=3, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s.%(funcName)s:%(lineno)d — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(fh)
    except Exception:
        pass  # non-critical: if file logging fails, console still works

def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Configures logging on first call."""
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(name)
