"""Platform patches applied at import time.

Windows CREATE_NO_WINDOW for every subprocess, and UTF-8 console reconfiguration
to survive non-UTF-8 code pages. Must be imported before anything that prints.
"""

import os as _os
import platform as _platform
import subprocess as _subprocess
import sys as _sys
from pathlib import Path as _Path

# PyInstaller bundles Playwright browsers beside OPERO.exe.  Tell Playwright
# about that deterministic location before any browser module is imported.
if getattr(_sys, "frozen", False):
    _browser_dir = _Path(_sys.executable).parent / "ms-playwright"
    if _browser_dir.is_dir():
        _os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(_browser_dir))
# ── Nuclear: force CREATE_NO_WINDOW on EVERY subprocess call on Windows ───────
if _platform.system() == "Windows":
    _OrigPopen = _subprocess.Popen

    class _Popen(_OrigPopen):
        def __init__(self, args, **kw):
            kw["creationflags"] = kw.get("creationflags", 0) | _subprocess.CREATE_NO_WINDOW
            kw.pop("startupinfo", None)
            super().__init__(args, **kw)

    _subprocess.Popen = _Popen


# ── Console must survive non-UTF-8 code pages ────────────────────────────────

for _stream in ("stdout", "stderr"):
    try:
        _s = getattr(_sys, _stream, None)
        if _s is not None and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
