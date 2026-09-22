param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$DistRoot = Join-Path $ProjectRoot "dist"
$BrowserRoot = Join-Path $env:LOCALAPPDATA "ms-playwright"

python -m PyInstaller --noconfirm --clean --onedir --windowed --name OPERO --icon config\jarvis.ico `
    --exclude-module PyQt6.QtWebEngineWidgets `
    --exclude-module PyQt6.QtWebEngineCore `
    --exclude-module PyQt6.QtWebChannel `
    --hidden-import unicodedata `
    --hidden-import idna `
    --hidden-import idna.core `
    --hidden-import httpx `
    --runtime-hook hooks\rthook_opero_qt.py `
    --add-binary "$env:LOCALAPPDATA\Programs\Python\Python312\DLLs\unicodedata.pyd;." `
    --upx-exclude unicodedata.pyd `
    --upx-exclude Qt6Core.dll `
    --upx-exclude Qt6Gui.dll `
    --upx-exclude Qt6Widgets.dll `
    --upx-exclude Qt6Network.dll `
    --upx-exclude Qt6Svg.dll `
    --upx-exclude Qt6Pdf.dll `
    --upx-exclude qwindows.dll `
    --upx-exclude opengl32sw.dll `
    --add-data "actions;actions" `
    --add-data "ui;ui" `
    --add-data "site;site" `
    --add-data "assets;assets" `
    --add-data "core\face_model.obj;core" `
    --add-data "core\prompt.txt;core" `
    --add-data "config\jarvis.ico;config" `
    --add-data "config\api_keys.example.json;config" `
    main.py

if (-not (Test-Path $BrowserRoot)) {
    throw "Playwright browsers are missing at $BrowserRoot. Run: python -m playwright install chromium"
}
Copy-Item -Recurse -Force $BrowserRoot (Join-Path $DistRoot "OPERO\ms-playwright")
Compress-Archive -Path (Join-Path $DistRoot "OPERO\*") -DestinationPath (Join-Path $DistRoot "OPERO-$Version-Portable.zip") -Force
Get-FileHash (Join-Path $DistRoot "OPERO\OPERO.exe") -Algorithm SHA256
