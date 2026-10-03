#computer_control.py
import json
import re
import string
import subprocess
import sys
import time
import random
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE         = _base_dir()
_CONFIG_PATH  = _BASE / "config" / "api_keys.json"
_MEMORY_PATH  = _BASE / "memory" / "long_term.json"

def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _get_os() -> str:
    return _load_config().get("os_system", "windows").lower()

_SAFE_SCREENSHOT_ROOTS = (
    Path.home(),
)

def _safe_screenshot_path(requested: str | None) -> Path:
    fallback = Path.home() / "Desktop" / "brahma_screenshot.png"
    if not requested:
        return fallback
    try:
        p = Path(requested).expanduser().resolve()
        for root in _SAFE_SCREENSHOT_ROOTS:
            if p.is_relative_to(root.resolve()):
                p.parent.mkdir(parents=True, exist_ok=True)
                return p
    except Exception:
        pass
    return fallback

def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")

_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Drew", "Quinn",
    "Avery", "Blake", "Cameron", "Dakota", "Emerson", "Finley", "Harper",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
]
_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "proton.me", "mail.com"]


def _random_data(data_type: str) -> str:
    dt = data_type.lower().strip()

    if dt == "first_name":
        return random.choice(_FIRST_NAMES)

    if dt == "last_name":
        return random.choice(_LAST_NAMES)

    if dt == "name":
        return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"

    if dt == "email":
        first = random.choice(_FIRST_NAMES).lower()
        last  = random.choice(_LAST_NAMES).lower()
        num   = random.randint(10, 999)
        return f"{first}.{last}{num}@{random.choice(_DOMAINS)}"

    if dt == "username":
        return f"{random.choice(_FIRST_NAMES).lower()}{random.randint(100, 9999)}"

    if dt == "password":
        chars = string.ascii_letters + string.digits + "!@#$%"
        raw   = (
            random.choice(string.ascii_uppercase)
            + random.choice(string.digits)
            + random.choice("!@#$%")
            + "".join(random.choices(chars, k=9))
        )
        return "".join(random.sample(raw, len(raw)))

    if dt == "phone":
        return f"+1{random.randint(200,999)}{random.randint(1_000_000, 9_999_999)}"

    if dt == "birthday":
        y = random.randint(1980, 2000)
        m = random.randint(1, 12)
        d = random.randint(1, 28)
        return f"{m:02d}/{d:02d}/{y}"

    if dt == "address":
        num    = random.randint(100, 9999)
        street = random.choice(["Main St", "Oak Ave", "Park Blvd", "Elm St", "Cedar Ln"])
        return f"{num} {street}"

    if dt == "zip_code":
        return str(random.randint(10000, 99999))

    if dt == "city":
        return random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"])

    return f"random_{data_type}_{random.randint(1000, 9999)}"

def _user_profile() -> dict:
    """Read identity fields from long-term memory."""
    try:
        if _MEMORY_PATH.exists():
            data     = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
            identity = data.get("identity", {})
            return {k: v.get("value", "") for k, v in identity.items()}
    except Exception:
        pass
    return {}

def _type(text: str, interval: float = 0.03) -> str:
    _require_pyautogui()
    time.sleep(0.3)
    pyautogui.typewrite(text, interval=interval)
    return f"Typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _smart_type(text: str, clear_first: bool = True) -> str:
    _require_pyautogui()
    if clear_first:
        _clear_field()
        time.sleep(0.1)

    if len(text) > 20 and _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        return f"Smart-typed (clipboard): {text[:60]}{'…' if len(text) > 60 else ''}"

    pyautogui.typewrite(text, interval=0.04)
    return f"Smart-typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _click(x=None, y=None, button: str = "left", clicks: int = 1) -> str:
    _require_pyautogui()
    if x is not None and y is not None:
        pyautogui.click(x, y, button=button, clicks=clicks)
        return f"{'Double-c' if clicks == 2 else 'C'}licked ({x}, {y}) [{button}]"
    pyautogui.click(button=button, clicks=clicks)
    return f"Clicked at current position [{button}]"


def _hotkey(*keys) -> str:
    _require_pyautogui()
    pyautogui.hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"


def _press(key: str) -> str:
    _require_pyautogui()
    pyautogui.press(key)
    return f"Pressed: {key}"


def _scroll(direction: str = "down", amount: int = 3) -> str:
    _require_pyautogui()
    vertical   = direction in ("up", "down")
    clicks     = amount if direction in ("up", "right") else -amount
    pyautogui.scroll(clicks) if vertical else pyautogui.hscroll(clicks)
    return f"Scrolled {direction} ×{amount}"


def _drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5,
          button: str = "left") -> str:
    _require_pyautogui()
    pyautogui.moveTo(x1, y1, duration=0.2)
    pyautogui.dragTo(x2, y2, duration=duration, button=button)
    return f"Dragged ({x1},{y1}) → ({x2},{y2}) [{button}]"


_EASES = {
    "linear": None,
    "ease_out": "easeOutQuad",
    "ease_in": "easeInQuad",
    "ease_in_out": "easeInOutQuad",
}


def _tween(ease: str):
    name = _EASES.get(str(ease or "").lower().strip(), "easeOutQuad")
    if name is None:
        return None
    return getattr(pyautogui, name, None)


def _move(x: int, y: int, duration: float = 0.3, ease: str = "ease_out") -> str:
    """Smooth cursor move; duration>0 eases along the tween (default ease-out)."""
    _require_pyautogui()
    duration = max(0.0, min(float(duration), 10.0))
    tween = _tween(ease)
    if tween is not None:
        pyautogui.moveTo(x, y, duration=duration, tween=tween)
    else:
        pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse → ({x}, {y}) in {duration}s"


def _move_relative(dx: int, dy: int, duration: float = 0.3, ease: str = "ease_out") -> str:
    """Relative move from the CURRENT cursor position."""
    _require_pyautogui()
    duration = max(0.0, min(float(duration), 10.0))
    tween = _tween(ease)
    if tween is not None:
        pyautogui.moveRel(int(dx), int(dy), duration=duration, tween=tween)
    else:
        pyautogui.moveRel(int(dx), int(dy), duration=duration)
    return f"Mouse moved by ({dx}, {dy})"


def _move_path(points, duration: float = 0.5, ease: str = "linear") -> str:
    """Move through a list of [x, y] waypoints in order (smooth path)."""
    _require_pyautogui()
    pts = _parse_points(points)
    if len(pts) < 2:
        return "move_path needs at least two [x, y] points."
    per_leg = max(0.05, min(float(duration), 30.0) / max(1, len(pts) - 1))
    tween = _tween(ease)
    for px, py in pts:
        if tween is not None:
            pyautogui.moveTo(px, py, duration=per_leg, tween=tween)
        else:
            pyautogui.moveTo(px, py, duration=per_leg)
    return f"Moved through {len(pts)} points ({duration}s total)"


def _parse_points(points) -> list[tuple[int, int]]:
    """Accept [[x,y], …] or 'x,y x,y …' — anything the model JSON-encodes."""
    out: list[tuple[int, int]] = []
    if isinstance(points, str):
        for pair in re.findall(r"(-?\d+)\s*,\s*(-?\d+)", points):
            out.append((int(pair[0]), int(pair[1])))
        return out
    if isinstance(points, (list, tuple)):
        for p in points:
            try:
                if isinstance(p, dict):
                    out.append((int(p.get("x")), int(p.get("y"))))
                else:
                    out.append((int(p[0]), int(p[1])))
            except (TypeError, ValueError, KeyError):
                continue
    return out


def _mouse_button_down(button: str = "left") -> str:
    _require_pyautogui()
    pyautogui.mouseDown(button=button)
    return f"Mouse {button} button DOWN"


def _mouse_button_up(button: str = "left") -> str:
    _require_pyautogui()
    pyautogui.mouseUp(button=button)
    return f"Mouse {button} button UP"


def _key_down(key: str) -> str:
    _require_pyautogui()
    pyautogui.keyDown(key)
    return f"Key held: {key}"


def _key_up(key: str) -> str:
    _require_pyautogui()
    pyautogui.keyUp(key)
    return f"Key released: {key}"


def _clipboard_get() -> str:
    if _PYPERCLIP:
        return pyperclip.paste()
    _hotkey("ctrl", "c")
    time.sleep(0.2)
    return "(copied — pyperclip unavailable for read)"


def _clipboard_paste(text: str) -> str:
    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        _require_pyautogui()
        pyautogui.hotkey("ctrl", "v")
        return f"Pasted: {text[:60]}{'…' if len(text) > 60 else ''}"
    return "pyperclip not available"


def _screenshot(save_path: str | None = None) -> str:
    _require_pyautogui()
    path = _safe_screenshot_path(save_path)
    img  = pyautogui.screenshot()
    img.save(str(path))
    return f"Screenshot saved: {path}"


def _clear_field() -> str:
    _require_pyautogui()
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    return "Field cleared"

def _focus_window(title: str) -> str:
    os_name = _get_os()

    if os_name == "windows":
        try:
            script = f'(New-Object -ComObject WScript.Shell).AppActivate("{title}")'
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (Windows) failed: {e}"

    if os_name == "mac":
        script = (
            f'tell application "System Events" to '
            f'set frontmost of (first process whose name contains "{title}") to true'
        )
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (macOS) failed: {e}"

    if os_name == "linux":
        try:
            result = subprocess.run(
                ["wmctrl", "-a", title],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                time.sleep(0.3)
                return f"Focused window: {title}"
        except FileNotFoundError:
            pass
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", title, "windowactivate"],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except FileNotFoundError:
            return "focus_window (Linux) requires wmctrl or xdotool"
        except Exception as e:
            return f"focus_window (Linux) failed: {e}"

    return f"focus_window: unknown OS '{os_name}'"


# ── spatial targeting: explicit x,y > window+anchor > monitor+anchor ─────────
def _resolve_point(params: dict) -> tuple[str, int | None, int | None]:
    """Resolve WHERE to act from spatial language, via the world model.

    Returns ("ok", x, y) for explicit/resolved coordinates, ("current", None,
    None) when no location was given (click at the cursor), or ("unresolved",
    None, None) when an anchor was given but nothing fits — the caller must
    fail loudly, never guess a point.
    """
    if params.get("x") is not None and params.get("y") is not None:
        try:
            return "ok", int(params.get("x")), int(params.get("y"))
        except (TypeError, ValueError):
            pass
    anchor = str(params.get("anchor", "") or "").strip()
    if not anchor:
        return "current", None, None

    from core.world_model import anchor_point, parse_spatial, pick_window, world
    rect = None
    wref = params.get("window") or params.get("title")
    if wref:
        matches = world().find_windows(str(wref))
        if not matches and parse_spatial(str(wref)):
            matches = world().windows()
        win = pick_window(matches, str(wref)) if matches else None
        rect = getattr(win, "rect", None) if win is not None else None
        if not rect:
            return "unresolved", None, None
    if rect is None:
        mons = world().monitors()
        try:
            idx = int(params.get("monitor", 0))
        except (TypeError, ValueError):
            idx = 0
        rect = mons[idx].rect if 0 <= idx < len(mons) else world().primary_rect()
    pt = anchor_point(tuple(rect) if rect else None, anchor)
    if pt is None:
        return "unresolved", None, None
    return "ok", pt[0], pt[1]


_UNRESOLVED = (
    "Could not resolve coordinates for anchor '{anchor}' (window={win}). "
    "Check the target with environment_status, or give explicit x,y."
)

# ── targeted window ops (win32): computer_settings' minimize/maximize act on
# the FOCUSED window; these act on the window matching `title` and verify.
_SW = {"minimize": 6, "maximize": 3, "restore": 9}


def _window_op(op: str, title: str) -> str:
    if _get_os() != "windows" or not title:
        return (f"window_{op} needs a title fragment and is implemented on Windows only "
                "(for the focused window use computer_settings minimize/maximize/close_window).")
    import ctypes
    from core.world_model import world

    w = world().find_windows(title)
    if not w:
        return f"No window matching '{title}' — check environment_status."
    target = w[0]
    hwnd = getattr(target, "hwnd", 0)
    if not hwnd:
        return f"Window '{target.title}' has no handle — cannot address it directly."
    user32 = ctypes.windll.user32
    label = (target.title or title)[:60]

    if op == "close":
        user32.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE
        for _ in range(20):
            time.sleep(0.1)
            world().invalidate()          # TTL cache would answer "still there"
            if not world().find_windows(title):
                return f"Closed window: {label} (verified: title gone)."
        return (f"WM_CLOSE sent to '{label}' but the window is still there — "
                "unsaved-work prompt may be waiting on screen. Check before retrying.")

    user32.ShowWindow(hwnd, _SW[op])
    time.sleep(0.2)
    world().invalidate()
    fresh = [x for x in world().find_windows(title) if getattr(x, "hwnd", 0) == hwnd]
    if not fresh:
        # minimize keeps the window in EnumWindows (visible=False) — re-read raw state
        try:
            import sys as _sys
            if _sys.platform == "win32" and user32.IsWindow(hwnd):
                if op == "minimize" and user32.IsIconic(hwnd):
                    return f"Minimized window: {label} (verified: IsIconic)."
                if op == "maximize" and user32.IsZoomed(hwnd):
                    return f"Maximized window: {label} (verified: IsZoomed)."
                if op == "restore" and not user32.IsIconic(hwnd) and not user32.IsZoomed(hwnd):
                    return f"Restored window: {label} (verified: normal state)."
        except Exception:
            pass
        return f"window_{op}: '{label}' could not be re-read after the change — state unverified."
    state = getattr(fresh[0], "state", "unknown")
    expected = {"minimize": "minimized", "maximize": "maximized", "restore": "normal"}[op]
    if state == expected:
        return f"{op.capitalize()}d window: {label} (verified: {state})."
    return f"window_{op} sent to '{label}' but state is '{state}', expected '{expected}'."


def _screen_find(description: str) -> tuple[int, int] | None:
    """Semantic screen targeting needs a vision model inside the tool — and
    this build has none (the old `llm_client` backend was orphaned). Refuse
    honestly instead of swallowing the ImportError and answering NOT_FOUND,
    which reads as 'the element does not exist' when really we never looked."""
    raise _VisionUnavailable(
        "screen_find/screen_click have no vision backend in this build. "
        "To act on something you can see: call screen_process (attaches a live "
        "screenshot), read the coordinates off it, then click with x,y "
        "(or window + anchor)."
    )


class _VisionUnavailable(RuntimeError):
    pass

def _button(params: dict) -> str:
    b = str(params.get("button", "left") or "left").lower()
    return b if b in ("left", "right", "middle") else "left"


def _fail_unresolved(params: dict) -> str:
    return _UNRESOLVED.format(
        anchor=params.get("anchor", ""),
        win=params.get("window") or params.get("title") or "(none)",
    )


def computer_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Dispatch table for all computer control actions.

    parameters keys (all optional unless noted):
      action        : (required) one of the actions listed below
      text          : text to type or paste
      x, y          : screen coordinates
      anchor        : spatial target — 'top-left', 'center', 'bottom right', …
                      resolved against `window` (title/spatial) or `monitor`
      window        : window title fragment (or 'the window on the right')
      monitor       : monitor index for an anchor (default: 0 = primary)
      button        : 'left' (default) | 'right' | 'middle'
      keys          : hotkey string, e.g. 'ctrl+c'
      key           : single key name, e.g. 'enter'
      direction     : 'up' | 'down' | 'left' | 'right'
      amount        : scroll amount (default: 3)
      seconds       : wait duration
      title         : window title fragment for focus_window / window_* ops
      duration      : seconds for move/drag (default 0.3; smooth tween)
      ease          : 'ease_out' (default) | 'ease_in' | 'ease_in_out' | 'linear'
      dx, dy        : relative mouse move
      points        : [[x,y], …] waypoints for move_path
      description   : natural-language element description (screen_find/click
                      are UNAVAILABLE in this build — see below)
      type          : data type for random_data
      field         : memory field name for user_data
      clear_first   : bool, clear field before typing (default: true)
      path          : save path for screenshot (must be inside home dir)

    Actions:
      type          — type text at cursor
      smart_type    — clear field + type (clipboard-backed)
      click         — click at x,y / anchor / current position
      double_click  — double click
      right_click   — right click
      move          — smooth move to x,y or anchor (duration + ease)
      move_relative — move dx,dy from current position
      move_path     — move through waypoints [[x,y], …]
      mouse_down/up — hold/release a mouse button (for custom drags)
      key_down/up   — hold/release a key (for custom chords)
      drag          — click-drag between two points (button honored)
      hotkey        — key combination
      press         — single key
      scroll        — scroll the wheel
      copy          — read clipboard
      paste         — write + paste clipboard
      screenshot    — capture screen (safe path only)
      wait          — sleep N seconds
      clear_field   — select-all + delete
      focus_window  — bring window to foreground
      window_minimize/maximize/restore/close — targeted at `title`, verified
      screen_find   — UNAVAILABLE (no vision backend); says so honestly
      screen_click  — UNAVAILABLE (no vision backend); says so honestly
      random_data   — generate fake form data
      user_data     — pull real data from memory
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    if not action:
        return "No action specified for computer_control."

    if player:
        player.write_log(f"[Computer] {action}")

    print(f"[ComputerControl] ▶ {action}  {params}")

    try:

        if action == "type":
            return _type(params.get("text", ""))

        if action == "smart_type":
            return _smart_type(
                params.get("text", ""),
                clear_first=params.get("clear_first", True),
            )

        if action in ("click", "left_click", "double_click", "right_click"):
            st, cx, cy = _resolve_point(params)
            if st == "unresolved":
                return _fail_unresolved(params)
            clicks = 2 if action == "double_click" else 1
            btn = "right" if action == "right_click" else _button(params)
            if st == "current":
                return _click(None, None, btn, clicks)
            return _click(cx, cy, btn, clicks)

        if action == "move":
            st, cx, cy = _resolve_point(params)
            if st == "unresolved":
                return _fail_unresolved(params)
            if st == "current":
                return "move needs a location: x,y or an anchor (e.g. anchor='top-left')."
            return _move(cx, cy,
                         duration=float(params.get("duration", 0.3)),
                         ease=str(params.get("ease", "ease_out")))

        if action == "move_relative":
            return _move_relative(int(params.get("dx", 0)), int(params.get("dy", 0)),
                                  duration=float(params.get("duration", 0.3)),
                                  ease=str(params.get("ease", "ease_out")))

        if action == "move_path":
            return _move_path(params.get("points"),
                              duration=float(params.get("duration", 0.5)),
                              ease=str(params.get("ease", "linear")))

        if action == "mouse_down":
            return _mouse_button_down(_button(params))

        if action == "mouse_up":
            return _mouse_button_up(_button(params))

        if action == "key_down":
            return _key_down(str(params.get("key", "shift")))

        if action == "key_up":
            return _key_up(str(params.get("key", "shift")))

        if action == "drag":
            return _drag(
                int(params.get("x1", 0)), int(params.get("y1", 0)),
                int(params.get("x2", 0)), int(params.get("y2", 0)),
                duration=float(params.get("duration", 0.5)),
                button=_button(params),
            )

        if action == "hotkey":
            raw  = params.get("keys", "")
            keys = [k.strip() for k in raw.split("+")] if isinstance(raw, str) else raw
            return _hotkey(*keys)

        if action == "press":
            return _press(params.get("key", "enter"))

        if action == "scroll":
            return _scroll(
                direction=params.get("direction", "down"),
                amount=int(params.get("amount", 3)),
            )

        if action == "copy":
            return _clipboard_get()

        if action == "paste":
            return _clipboard_paste(params.get("text", ""))

        if action == "screenshot":
            return _screenshot(params.get("path"))

        if action == "screen_find":
            try:
                coords = _screen_find(params.get("description", ""))
            except _VisionUnavailable as e:
                return f"UNAVAILABLE: {e}"
            return f"{coords[0]},{coords[1]}" if coords else "NOT_FOUND"

        if action == "screen_click":
            desc = params.get("description", "")
            try:
                coords = _screen_find(desc)
            except _VisionUnavailable as e:
                return f"UNAVAILABLE: {e}"
            if coords:
                time.sleep(0.2)
                _click(x=coords[0], y=coords[1])
                return f"Clicked '{desc}' at {coords}"
            return f"Element not found on screen: '{desc}'"

        if action == "wait":
            secs = float(params.get("seconds", 1.0))
            secs = min(secs, 30.0)
            time.sleep(secs)
            return f"Waited {secs}s"

        if action == "clear_field":
            return _clear_field()

        if action == "focus_window":
            return _focus_window(params.get("title", ""))

        if action in ("window_minimize", "window_maximize", "window_restore", "window_close"):
            return _window_op(action.split("_", 1)[1], str(params.get("title", "")))

        if action == "random_data":
            dt     = params.get("type", "name")
            result = _random_data(dt)
            print(f"[ComputerControl] 🎲 random {dt} → {result}")
            return result

        if action == "user_data":
            field   = params.get("field", "name")
            profile = _user_profile()
            value   = profile.get(field, "")
            if not value:
                value = _random_data(field)
                print(f"[ComputerControl] ⚠️ No '{field}' in memory, using random: {value}")
            return value

        return f"Unknown action: '{action}'"

    except Exception as e:
        print(f"[ComputerControl] ❌ {action}: {e}")
        return f"computer_control '{action}' failed: {e}"

# ── OPERO tool registration ───────────────────────────────────────────────────
TOOL = {
    "name": "computer_control",
    "description": (
        "Mouse and keyboard automation by coordinates or by spatial language: "
        "click/move/drag at x,y or at an anchor ('top-left', 'center') of a window "
        "(by title, e.g. window='Notepad') or monitor, smooth moves with duration/ease, "
        "relative moves and waypoint paths, mouse/key down-up for custom gestures, typing, "
        "hotkeys, key presses, scroll, copy/paste, screenshot, targeted window "
        "minimize/maximize/restore/close by title (verified after acting), focus a window, "
        "clear a field, wait, fill random/user form data. screen_find/screen_click are "
        "UNAVAILABLE in this build — to click something you can see, take screen_process "
        "and give x,y. For OS settings (volume, brightness, Wi-Fi, virtual desktops, "
        "app search) use computer_settings instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "type | smart_type | click | double_click | right_click | move | "
                    "move_relative | move_path | mouse_down | mouse_up | key_down | key_up | "
                    "drag | hotkey | press | scroll | copy | paste | screenshot | "
                    "screen_find | screen_click | wait | clear_field | focus_window | "
                    "window_minimize | window_maximize | window_restore | window_close | "
                    "random_data | user_data"
                ),
            },
            "text": {"type": "STRING", "description": "Text to type or paste (type/smart_type)."},
            "x": {"type": "NUMBER", "description": "Screen X coordinate."},
            "y": {"type": "NUMBER", "description": "Screen Y coordinate."},
            "anchor": {"type": "STRING", "description": "Spatial target: top-left, top, bottom right, center, left, right, … resolved against `window` (or `monitor` when no window is given)."},
            "window": {"type": "STRING", "description": "Window title fragment (or spatial phrase like 'the window on the right') for `anchor` resolution."},
            "monitor": {"type": "NUMBER", "description": "Monitor index for anchors without a window (default 0 = primary)."},
            "dx": {"type": "NUMBER", "description": "Relative mouse move: X delta (move_relative)."},
            "dy": {"type": "NUMBER", "description": "Relative mouse move: Y delta (move_relative)."},
            "points": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "NUMBER"}}, "description": "Waypoints [[x,y], …] for move_path."},
            "duration": {"type": "NUMBER", "description": "Seconds for move/drag/move_path (smooth tween; default 0.3)."},
            "ease": {"type": "STRING", "description": "ease_out (default) | ease_in | ease_in_out | linear."},
            "x1": {"type": "NUMBER", "description": "Drag start X."},
            "y1": {"type": "NUMBER", "description": "Drag start Y."},
            "x2": {"type": "NUMBER", "description": "Drag end X."},
            "y2": {"type": "NUMBER", "description": "Drag end Y."},
            "button": {"type": "STRING", "description": "left (default) | right | middle — honored by click, drag, mouse_down/up."},
            "keys": {"type": "STRING", "description": "Hotkey combination, e.g. ctrl+c."},
            "key": {"type": "STRING", "description": "Single key name, e.g. enter, esc, tab (also key_down/key_up)."},
            "direction": {"type": "STRING", "description": "up | down | left | right for scroll."},
            "amount": {"type": "NUMBER", "description": "Scroll amount (default: 3)."},
            "seconds": {"type": "NUMBER", "description": "Wait duration in seconds (max 30)."},
            "title": {"type": "STRING", "description": "Window title fragment for focus_window and window_minimize/maximize/restore/close."},
            "description": {"type": "STRING", "description": "Element description for screen_find/screen_click (UNAVAILABLE in this build — use screen_process + x,y)."},
            "type": {"type": "STRING", "description": "Data type for random_data (name, email, phone...)."},
            "field": {"type": "STRING", "description": "Memory field name for user_data."},
            "clear_first": {"type": "BOOLEAN", "description": "Clear the field before typing (default: true)."},
            "path": {"type": "STRING", "description": "Screenshot save path (must be inside the home directory)."},
        },
        "required": ["action"],
    },
    "handler": computer_control,
}
