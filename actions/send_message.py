import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.06
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

def _get_os() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg.get("os_system", "windows").lower()
    except Exception:
        return "windows"


def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")


def _paste_text(text: str) -> None:
    _require_pyautogui()

    os_name = _get_os()
    paste_hotkey = ("command", "v") if os_name == "mac" else ("ctrl", "v")

    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.15)
        pyautogui.hotkey(*paste_hotkey)
        time.sleep(0.1)
    else:
        pyautogui.write(text, interval=0.03)


def _clear_and_paste(text: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    select_all = ("command", "a") if os_name == "mac" else ("ctrl", "a")
    pyautogui.hotkey(*select_all)
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    _paste_text(text)

def _open_app(app_name: str) -> bool:
    _require_pyautogui()
    os_name = _get_os()

    try:
        if os_name == "windows":
            pyautogui.press("win")
            time.sleep(0.5)
            _paste_text(app_name)
            time.sleep(0.6)
            pyautogui.press("enter")
            time.sleep(2.5)
            return True

        elif os_name == "mac":
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["open", "-a", f"{app_name}.app"],
                    capture_output=True, text=True, timeout=10,
                )
            time.sleep(2.5)
            return result.returncode == 0

        else: 
            launched = False
            for launcher in [
                ["gtk-launch", app_name.lower()],
                [app_name.lower()],
            ]:
                try:
                    subprocess.Popen(
                        launcher,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            time.sleep(2.5)
            return launched

    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open {app_name}: {e}")
        return False


def _open_browser_url(url: str) -> bool:
    import webbrowser
    try:
        webbrowser.open(url)
        time.sleep(4.0) 
        return True
    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open browser: {e}")
        return False

def _search_in_app(query: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    search_hotkey = ("command", "f") if os_name == "mac" else ("ctrl", "f")

    pyautogui.hotkey(*search_hotkey)
    time.sleep(0.5)
    _clear_and_paste(query)
    time.sleep(1.0)

def _desktop_send(app_name: str, receiver: str, message: str) -> str:
    if not _open_app(app_name):
        return f"Could not open {app_name}."

    time.sleep(1.0)
    _search_in_app(receiver)
    pyautogui.press("enter")
    time.sleep(0.8)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)
    return f"Message sent to {receiver} via {app_name}."
def _send_whatsapp(receiver: str, message: str) -> str:
    return _desktop_send("WhatsApp", receiver, message)


def _whatsapp_call(receiver: str, call_type: str = "voice") -> str:
    """Make a WhatsApp voice or video call via WhatsApp Desktop automation."""
    _require_pyautogui()

    if not _open_app("WhatsApp"):
        return "Could not open WhatsApp Desktop."

    time.sleep(1.5)

    # Search for the contact
    _search_in_app(receiver)
    time.sleep(0.8)
    pyautogui.press("enter")
    time.sleep(1.0)

    # Click the call button (top-right area of chat)
    # In WhatsApp Desktop, the phone icon is near the top-right
    # Use keyboard shortcut: Ctrl+Shift+C opens call menu, or click the icon
    # Safer approach: use Alt+C shortcut to start a voice call in the chat
    # Actually, WhatsApp Desktop doesn't have a reliable keyboard shortcut for calls.
    # We'll click the call icon by locating it on screen.

    import pyautogui

    # Try to find and click the call button by image or position
    # WhatsApp Desktop call button is typically in the top toolbar area
    # We'll use a reliable coordinate-based approach

    # Anchor to WhatsApp's own window rather than the full screen.  A full-screen
    # percentage breaks as soon as the app sits on a second monitor or is tiled.
    try:
        import pygetwindow as gw
        windows = [w for w in gw.getAllWindows() if "whatsapp" in w.title.lower()]
        wa = next((w for w in windows if w.width > 300 and w.height > 300), None)
        if wa:
            wa.activate()
            time.sleep(0.3)
            call_x = wa.left + int(wa.width * 0.86)
            call_y = wa.top + int(wa.height * 0.055)
        else:
            raise RuntimeError("WhatsApp window not found")
    except Exception:
        screen_w, screen_h = pyautogui.size()
        call_x, call_y = int(screen_w * 0.80), int(screen_h * 0.04)

    if call_type == "video":
        # Video call is slightly to the right of voice call
        call_x = int(screen_w * 0.84)

    pyautogui.click(call_x, call_y)
    time.sleep(1.0)

    # If it's a video call, there might be a confirmation dialog
    if call_type == "video":
        time.sleep(0.5)

    return f"WhatsApp {call_type} call started with {receiver}."


def _whatsapp_end_call() -> str:
    """End the current WhatsApp call."""
    _require_pyautogui()
    import pyautogui

    # The end call button is typically in the center-bottom area
    # Red phone icon
    screen_w, screen_h = pyautogui.size()
    end_x = int(screen_w * 0.50)
    end_y = int(screen_h * 0.85)

    pyautogui.click(end_x, end_y)
    time.sleep(0.5)
    return "Call ended."


def _send_telegram(receiver: str, message: str) -> str:
    return _desktop_send("Telegram", receiver, message)

def _send_signal(receiver: str, message: str) -> str:
    return _desktop_send("Signal", receiver, message)


def _send_discord(receiver: str, message: str) -> str:
    return _desktop_send("Discord", receiver, message)


def _send_instagram(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.instagram.com/direct/new/"):
        return "Could not open Instagram in browser."

    _paste_text(receiver)
    time.sleep(1.5)

    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")   
    time.sleep(0.4)

    for _ in range(4):
        pyautogui.press("tab")
        time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(2.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Instagram."


def _send_messenger(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.messenger.com/"):
        return "Could not open Messenger in browser."


    _search_in_app(receiver)
    time.sleep(0.5)
    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(1.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Messenger."

_PLATFORM_MAP = [
    ({"whatsapp", "wp", "wapp"},              _send_whatsapp),
    ({"telegram", "tg"},                      _send_telegram),
    ({"instagram", "ig", "insta"},            _send_instagram),
    ({"signal"},                               _send_signal),
    ({"discord"},                              _send_discord),
    ({"messenger", "facebook", "fb"},         _send_messenger),
]


def _resolve_platform(platform_str: str):
    key = platform_str.lower().strip()
    for keywords, handler in _PLATFORM_MAP:
        if any(k in key for k in keywords):
            return handler
    return lambda r, m: _desktop_send(platform_str.strip().title(), r, m)


def send_message(
    parameters: dict,
    response=None,
    player=None,
    speak=None,
    session_memory=None,
) -> str:
    params       = parameters or {}
    receiver     = params.get("receiver", "").strip()
    message_text = params.get("message_text", "").strip()
    platform     = params.get("platform", "whatsapp").strip()
    action       = params.get("action", "message").strip().lower()

    if not _PYAUTOGUI:
        return "PyAutoGUI is not installed — cannot control the desktop."

    # ── Call actions ──────────────────────────────────────────────────────
    if action in ("voice_call", "video_call", "call"):
        if not receiver:
            return "Please specify who to call."
        call_type = "video" if action == "video_call" else "voice"
        print(f"[SendMessage] 📞 WhatsApp {call_type} call → {receiver}")
        if player:
            player.write_log(f"[msg] WhatsApp {call_type} call → {receiver}")
        try:
            result = _whatsapp_call(receiver, call_type)
            # A virtual microphone is intentionally a user-controlled routing
            # choice: without it, playing TTS locally must never be claimed as
            # speech delivered to the person on the call.
            if "started" in result.lower() and message_text and callable(speak):
                speak(
                    "Read this call opener exactly, with no introduction or extra words: "
                    + message_text
                )
                result += (
                    " OPERO is reading the supplied opener now. It reaches the caller "
                    "only when WhatsApp's microphone is routed to OPERO audio (for example, VB-CABLE)."
                )
        except Exception as e:
            result = f"Could not start call: {e}"
        print(f"[SendMessage] {'✅' if 'started' in result.lower() else '❌'} {result}")
        if player:
            player.write_log(f"[msg] {result}")
        return result

    if action == "end_call":
        print("[SendMessage] 📞 Ending call")
        if player:
            player.write_log("[msg] Ending call")
        try:
            result = _whatsapp_end_call()
        except Exception as e:
            result = f"Could not end call: {e}"
        return result

    # ── Message actions ───────────────────────────────────────────────────
    if not receiver:
        return "Please specify a recipient."
    if not message_text:
        return "Please specify the message content."

    preview = message_text[:50] + ("…" if len(message_text) > 50 else "")
    print(f"[SendMessage] 📨 {platform} → {receiver}: {preview}")
    if player:
        player.write_log(f"[msg] {platform} → {receiver}")

    try:
        handler = _resolve_platform(platform)
        result  = handler(receiver, message_text)
    except Exception as e:
        result = f"Could not send message: {e}"

    print(f"[SendMessage] {'✅' if 'sent' in result.lower() else '❌'} {result}")
    if player:
        player.write_log(f"[msg] {result}")

    return result


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "send_message",
    "description": (
        "Sends a message or makes a call via WhatsApp, Telegram, or other platform. "
        "Supports: message, voice_call, video_call, end_call actions. "
        "For WhatsApp calls, it opens WhatsApp Desktop and clicks the call button."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "receiver": {
                "type": "STRING",
                "description": "Recipient contact name",
            },
            "message_text": {
                "type": "STRING",
                "description": "The message to send (required for message action)",
            },
            "platform": {
                "type": "STRING",
                "description": "Platform: WhatsApp, Telegram, Signal, Discord, etc.",
            },
            "action": {
                "type": "STRING",
                "description": (
                    "Action to perform: message (default), voice_call, video_call, end_call. "
                    "For a call, message_text is the optional opening line OPERO reads after the call starts. "
                    "voice_call/video_call open WhatsApp Desktop and start a call with the receiver."
                ),
            },
        },
        "required": ["receiver", "platform"],
    },
    "handler": send_message,
}
