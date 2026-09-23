@echo off
REM ===========================================================================
REM Reproducible OPERO dev-environment bootstrap (Windows).
REM
REM Mirrors the repo's declared mechanisms:
REM   README quick start : python -m pip install -r requirements.txt
REM   CI (.github/workflows/ci.yml):
REM     python -m pip install --upgrade pip
REM     python -m pip install -e ".[dev]"
REM
REM Two Windows-specific environment fixes, no application code touched:
REM   1. PYTHONUTF8=1 — setup.py prints non-ASCII glyphs; the default cp1252
REM      console encoding crashes pip's build backend (UnicodeEncodeError).
REM   2. --no-build-isolation — setup.py's main() executes inside pip's PEP 517
REM      metadata hook and spawns a nested "python -m pip install -r
REM      requirements.txt". pip's isolated-build environment hides pip from that
REM      nested interpreter on a Windows venv ("No module named pip"); CI's Linux
REM      system Python is unaffected. Requires setuptools+wheel (pyproject
REM      [build-system] requires) present in the venv first — hence step 3.
REM ===========================================================================
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe

%PY% -m pip install --upgrade pip
if errorlevel 1 exit /b 1

%PY% -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

%PY% -m pip install "setuptools>=68.0" wheel
if errorlevel 1 exit /b 1

%PY% -m pip install --no-build-isolation -e ".[dev]"
if errorlevel 1 (
    REM -----------------------------------------------------------------------
    REM KNOWN PRE-EXISTING PACKAGING ISSUE (not environment, not tests):
    REM setup.py contains no setup() call — it is a standalone installer
    REM script (README: "python setup.py"). setuptools' editable-metadata step
    REM therefore aborts with "Exactly one .egg-info should have been produced,
    REM but found 0". This fails identically on any platform/pip mode.
    REM Fall back to installing the [project.optional-dependencies].dev set
    REM declared in pyproject.toml directly, so the test toolchain matches CI.
    REM -----------------------------------------------------------------------
    echo [fallback] installing declared dev extras directly from pyproject.toml
    %PY% -m pip install "pytest>=7.0" "ruff>=0.4" "mypy>=1.0" "black>=24.0"
    if errorlevel 1 exit /b 1
)

%PY% -m pip check
exit /b %ERRORLEVEL%