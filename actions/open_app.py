# actions/open_app.py
# Brahma AI - Cross-Platform App Launcher

import os
import time
import subprocess
import platform
import shutil

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

_APP_ALIASES = {
    "whatsapp":           {"Windows": "WhatsApp",               "Darwin": "WhatsApp",            "Linux": "whatsapp"},
    "chrome":             {"Windows": "chrome",                 "Darwin": "Google Chrome",       "Linux": "google-chrome"},
    "google chrome":      {"Windows": "chrome",                 "Darwin": "Google Chrome",       "Linux": "google-chrome"},
    "firefox":            {"Windows": "firefox",                "Darwin": "Firefox",             "Linux": "firefox"},
    "spotify":            {"Windows": "Spotify",                "Darwin": "Spotify",             "Linux": "spotify"},
    "vscode":             {"Windows": "code",                   "Darwin": "Visual Studio Code",  "Linux": "code"},
    "visual studio code": {"Windows": "code",                   "Darwin": "Visual Studio Code",  "Linux": "code"},
    "discord":            {"Windows": "Discord",                "Darwin": "Discord",             "Linux": "discord"},
    "telegram":           {"Windows": "Telegram",               "Darwin": "Telegram",            "Linux": "telegram"},
    "instagram":          {"Windows": "Instagram",              "Darwin": "Instagram",           "Linux": "instagram"},
    "tiktok":             {"Windows": "TikTok",                 "Darwin": "TikTok",              "Linux": "tiktok"},
    "notepad":            {"Windows": "notepad.exe",            "Darwin": "TextEdit",            "Linux": "gedit"},
    "calculator":         {"Windows": "calc.exe",               "Darwin": "Calculator",          "Linux": "gnome-calculator"},
    "terminal":           {"Windows": "cmd.exe",                "Darwin": "Terminal",            "Linux": "gnome-terminal"},
    "cmd":                {"Windows": "cmd.exe",                "Darwin": "Terminal",            "Linux": "bash"},
    "explorer":           {"Windows": "explorer.exe",           "Darwin": "Finder",              "Linux": "nautilus"},
    "file explorer":      {"Windows": "explorer.exe",           "Darwin": "Finder",              "Linux": "nautilus"},
    "paint":              {"Windows": "mspaint.exe",            "Darwin": "Preview",             "Linux": "gimp"},
    "word":               {"Windows": "winword",                "Darwin": "Microsoft Word",      "Linux": "libreoffice --writer"},
    "excel":              {"Windows": "excel",                  "Darwin": "Microsoft Excel",     "Linux": "libreoffice --calc"},
    "powerpoint":         {"Windows": "powerpnt",               "Darwin": "Microsoft PowerPoint","Linux": "libreoffice --impress"},
    "vlc":                {"Windows": "vlc",                    "Darwin": "VLC",                 "Linux": "vlc"},
    "zoom":               {"Windows": "Zoom",                   "Darwin": "zoom.us",             "Linux": "zoom"},
    "slack":              {"Windows": "Slack",                  "Darwin": "Slack",               "Linux": "slack"},
    "steam":              {"Windows": "steam",                  "Darwin": "Steam",               "Linux": "steam"},
    "task manager":       {"Windows": "taskmgr.exe",            "Darwin": "Activity Monitor",    "Linux": "gnome-system-monitor"},
    "settings":           {"Windows": "ms-settings:",           "Darwin": "System Preferences",  "Linux": "gnome-control-center"},
    "powershell":         {"Windows": "powershell.exe",         "Darwin": "Terminal",            "Linux": "bash"},
    "edge":               {"Windows": "msedge",                 "Darwin": "Microsoft Edge",      "Linux": "microsoft-edge"},
    "brave":              {"Windows": "brave",                  "Darwin": "Brave Browser",       "Linux": "brave-browser"},
    "obsidian":           {"Windows": "Obsidian",               "Darwin": "Obsidian",            "Linux": "obsidian"},
    "notion":             {"Windows": "Notion",                 "Darwin": "Notion",              "Linux": "notion"},
    "blender":            {"Windows": "blender",                "Darwin": "Blender",             "Linux": "blender"},
    "capcut":             {"Windows": "CapCut",                 "Darwin": "CapCut",              "Linux": "capcut"},
    "postman":            {"Windows": "Postman",                "Darwin": "Postman",             "Linux": "postman"},
    "figma":              {"Windows": "Figma",                  "Darwin": "Figma",               "Linux": "figma"},
}


def _token_contains(hay: str, needle: str) -> bool:
    """True when needle's words appear contiguously in hay's words.

    Replaces the old bidirectional substring test that fired cross-aliases:
    alias 'word' matched request 'wordpad' and launched WinWord instead.
    """
    h, n = hay.split(), needle.split()
    if not n:
        return False
    return any(h[i:i + len(n)] == n for i in range(len(h) - len(n) + 1))


def _normalize(raw: str) -> str:
    system = platform.system()
    key    = raw.lower().strip()
    if key in _APP_ALIASES:
        return _APP_ALIASES[key].get(system, raw)
    for alias_key, os_map in _APP_ALIASES.items():
        if _token_contains(key, alias_key):
            return os_map.get(system, raw)
    return raw


def _is_running(app_name: str) -> bool:
    if not _PSUTIL:
        return True
    app_lower = app_name.lower().replace(" ", "").replace(".exe", "")
    try:
        for proc in psutil.process_iter(["name"]):
            try:
                proc_name = proc.info["name"].lower().replace(" ", "").replace(".exe", "")
                if app_lower in proc_name or proc_name in app_lower:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return False


def _find_window(app_name: str):
    """First open window whose title/process matches this app, or None."""
    try:
        from core.perception import get_open_windows
        key = app_name.lower().strip()
        for w in get_open_windows():
            hay = f"{w.title or ''} {w.process or ''}".lower()
            proc = (w.process or "").lower().replace(".exe", "")
            if key in hay or (proc and proc in key.replace(" ", "")):
                return w
    except Exception:
        return None
    return None


def _focus_existing(app_name: str):
    """Reuse path: focus an already-open window of this app.

    Returns (window_title, verified) — verified is None when the foreground
    could not be re-read — or None when no matching window exists (caller
    launches a fresh instance instead).
    """
    w = _find_window(app_name)
    if w is None:
        return None
    try:
        from actions.computer_control import _focus_window
        res = _focus_window(w.title or app_name)
    except Exception:
        return None
    if not str(res).startswith("Focused window"):
        return None
    verified = None
    try:
        from core.perception import get_active_window
        fg = get_active_window()
        if fg is not None:
            title_frag = (w.title or "")[:20].lower()
            fg_hay = f"{fg.title or ''} {fg.process or ''}".lower()
            verified = bool(title_frag) and title_frag in fg_hay
    except Exception:
        verified = None
    return (w.title or app_name, verified)


def _verify_launch(app_name: str, was_running: bool, timeout: float = 4.0) -> bool | None:
    """Poll for the app's process after a launch attempt.

    True = running now, False = never appeared, None = cannot verify
    (psutil unavailable). `was_running` short-circuits to True: the process
    was already active, so a process check cannot prove a *new* instance —
    the caller words its result accordingly.
    """
    if not _PSUTIL:
        return None
    if was_running:
        return True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _is_running(app_name):
            return True
        time.sleep(0.3)
    return False


def _launch_windows(app_name: str) -> bool:
    app_lower = app_name.lower().strip()

    # Direct Chrome launching
    if app_lower in ("chrome", "google chrome", "browser", "internet", "web"):
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            shutil.which("chrome"),
        ]
        for cp in chrome_paths:
            if cp and (os.path.exists(cp) if os.path.isabs(cp) else True):
                try:
                    subprocess.Popen([cp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(1.0)
                    return True
                except Exception:
                    pass

    # Direct Spotify launching (app or Chrome web player fallback)
    if app_lower in ("spotify", "spotify music", "spotify web"):
        spotify_paths = [
            os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Spotify\Spotify.exe"),
            r"C:\Program Files\Spotify\Spotify.exe",
            shutil.which("spotify"),
        ]
        for sp in spotify_paths:
            if sp and os.path.exists(sp):
                try:
                    subprocess.Popen([sp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(1.0)
                    return True
                except Exception:
                    pass

        # If Spotify desktop is not installed, open Spotify in Google Chrome
        from plugins.spotify_controller import _open_url_in_chrome
        _open_url_in_chrome("https://open.spotify.com")
        time.sleep(1.0)
        return True

    # Try direct binary in PATH or Windows System32
    bin_path = shutil.which(app_name) or shutil.which(f"{app_name}.exe")
    if bin_path:
        try:
            subprocess.Popen([bin_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
            return True
        except Exception:
            pass

    # Fallback to Start Menu search
    try:
        import pyautogui
        pyautogui.PAUSE = 0.1
        pyautogui.press("win")
        time.sleep(0.6)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(3.0)
        return True
    except Exception as e:
        print(f"[open_app] ⚠️ Windows launch failed: {e}")
        return False

def _launch_macos(app_name: str) -> bool:
    try:
        result = subprocess.run(["open", "-a", app_name], capture_output=True, timeout=8)
        if result.returncode == 0:
            time.sleep(1.0)
            return True
    except Exception:
        pass

    try:
        result = subprocess.run(["open", "-a", f"{app_name}.app"], capture_output=True, timeout=8)
        if result.returncode == 0:
            time.sleep(1.0)
            return True
    except Exception:
        pass

    try:
        import pyautogui
        pyautogui.hotkey("command", "space")
        time.sleep(0.6)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(1.5)
        return True
    except Exception as e:
        print(f"[open_app] ⚠️ macOS Spotlight failed: {e}")
        return False



def _launch_linux(app_name: str) -> bool:
    binary = (
        shutil.which(app_name) or
        shutil.which(app_name.lower()) or
        shutil.which(app_name.lower().replace(" ", "-"))
    )
    if binary:
        try:
            subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
            return True
        except Exception:
            pass

    try:
        subprocess.run(["xdg-open", app_name], capture_output=True, timeout=5)
        return True
    except Exception:
        pass

    try:
        desktop_name = app_name.lower().replace(" ", "-")
        subprocess.run(["gtk-launch", desktop_name], capture_output=True, timeout=5)
        return True
    except Exception:
        pass

    return False


_OS_LAUNCHERS = {
    "Windows": _launch_windows,
    "Darwin":  _launch_macos,
    "Linux":   _launch_linux,
}


def open_app(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    app_name = params.get("app_name", "").strip()

    if not app_name:
        return "Please specify which application to open, sir."

    system   = platform.system()
    launcher = _OS_LAUNCHERS.get(system)

    if launcher is None:
        return f"Unsupported OS: {system}"

    normalized = _normalize(app_name)
    new_window = bool(params.get("new_window"))

    # Reuse first: if the app already has a window and the user did not ask
    # for a new instance, bring that window forward instead of spawning.
    was_running = _is_running(normalized) or _is_running(app_name)
    if was_running and not new_window:
        focus = _focus_existing(app_name)
        if focus is not None:
            title, verified = focus
            _note(app_name, verified=True)
            if verified:
                return f"{app_name} was already open — focused its existing window (verified in front): {title}"
            return (f"{app_name} was already open — asked the OS to focus its window: {title} "
                    f"(foreground could not be re-read to verify).")

    print(f"[open_app] 🚀 Launching: {app_name} → {normalized} ({system})")

    if player:
        player.write_log(f"[open_app] {app_name}")

    try:
        success = launcher(normalized)

        if not success and normalized != app_name:
            success = launcher(app_name)

        if success:
            verified = _verify_launch(app_name, was_running)
            _note(app_name, verified=bool(verified))
            if verified is None:
                return f"Launched {app_name}, but I cannot verify it is running (process check unavailable)."
            if verified:
                if was_running:
                    return f"Opened {app_name} — verified: its process is running."
                return f"Opened {app_name} — verified: it is now running."
            return f"Launched {app_name}, but I could NOT verify it is running — it may not have started."

        return (
            f"I tried to open {app_name}, sir, but couldn't confirm it launched. "
            f"It may still be loading or might not be installed."
        )

    except Exception as e:
        print(f"[open_app] ❌ {e}")
        return f"Failed to open {app_name}, sir: {e}"


def _note(app_name: str, verified: bool) -> None:
    """Record the app as the current task resource for reference resolution."""
    try:
        from core.context import task_ctx
        task_ctx().note_resource("application", app_name, label=app_name, verified=verified)
    except Exception:
        pass

# ── OPERO tool registration ───────────────────────────────────────────────────
TOOL = {
    "name": "open_app",
    "description": (
        "Open a desktop application (chrome, vscode, spotify, whatsapp, calculator, "
        "excel, telegram, steam...) on Windows, macOS or Linux. REUSE: if the app is "
        "already open, its existing window is focused instead of launching a duplicate "
        "— pass new_window=true only when the user explicitly wants another instance "
        "('new window', 'open it again'). The result states whether the launch was "
        "verified (process observed running) or unverified — never claim more. "
        "To interact inside the app afterwards, follow up with computer_control."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {"type": "STRING", "description": "Application name or friendly alias to launch."},
            "new_window": {"type": "BOOLEAN", "description": "Force a new instance even if the app is already open (default false = reuse/focus)."},
        },
        "required": ["app_name"],
    },
    "handler": open_app,
}
