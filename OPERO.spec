# -*- mode: python ; coding: utf-8 -*-

import sys
import sysconfig
from pathlib import Path

# unicodedata is a CPython extension required by idna/httpx/google.genai.
# Force-include it so COLLECT always ships it (missing → ModuleNotFoundError).
_dll_dir = Path(sysconfig.get_path("platstdlib")) / "DLLs"
if not (_dll_dir / "unicodedata.pyd").is_file():
    _dll_dir = Path(sys.executable).parent / "DLLs"
_unicodedata = _dll_dir / "unicodedata.pyd"
_binaries = []
if _unicodedata.is_file():
    _binaries.append((str(_unicodedata), "."))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_binaries,
    datas=[('actions', 'actions'), ('ui', 'ui'), ('site', 'site'), ('assets', 'assets'), ('core/face_model.obj', 'core'), ('core/prompt.txt', 'core'), ('config/jarvis.ico', 'config'), ('config/api_keys.example.json', 'config')],
    hiddenimports=['unicodedata', 'idna', 'idna.core', 'httpx'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebChannel'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OPERO',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['config/jarvis.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['unicodedata.pyd', 'python3.dll', 'python312.dll'],
    name='OPERO',
)
