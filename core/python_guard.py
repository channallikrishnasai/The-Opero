"""Startup guard: refuse to run OPERO on an unsupported Python interpreter.

OPERO requires Python >= 3.11 (``asyncio.TaskGroup``, ``BaseExceptionGroup``,
``enum.StrEnum``). Launching under Python 3.10 used to die deep inside the
Gemini Live session with an obscure ``asyncio`` traceback (see
``FATAL_CRASH.log``); this guard converts that into one clear line at startup.
``core.patches`` calls it immediately after import, and ``main.py`` loads
``core.patches`` first, so it runs before any project module.
"""

from __future__ import annotations

import sys

MIN_PYTHON: tuple[int, int] = (3, 11)


def version_error(version_info: tuple[int, ...], executable: str) -> str:
    return (
        f"OPERO requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ but is running "
        f"Python {version_info[0]}.{version_info[1]}.{version_info[2]} ({executable}).\n"
        "Recreate the environment with a supported interpreter, e.g.: py -3.11 -m venv .venv"
    )


def ensure_supported(
    version_info: tuple[int, ...] | None = None,
    executable: str | None = None,
) -> None:
    """Exit with a clear message when running on Python < 3.11."""
    if version_info is None:
        version_info = sys.version_info
    if executable is None:
        executable = sys.executable
    if version_info < MIN_PYTHON:
        raise SystemExit(version_error(version_info, executable))
