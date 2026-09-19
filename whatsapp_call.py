"""
whatsapp_call.py — OPERO WhatsApp Call Detection & Control

Communicates with the Node.js whatsapp-web.js bridge to detect incoming
WhatsApp calls and control them (answer/reject via PyAutoGUI).
"""

import subprocess
import sys
import time
import json
import os
import threading
import shutil
import numpy as np
from pathlib import Path
from typing import Optional, Callable

from core.logger import get_logger
log = get_logger(__name__)

try:
    import requests
except ImportError:
    requests = None

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False

BRIDGE_DIR = Path(__file__).parent / "whatsapp_bridge"
BRIDGE_JS = BRIDGE_DIR / "bridge.js"
BRIDGE_PORT = 8099
BRIDGE_URL = f"http://127.0.0.1:{BRIDGE_PORT}"


class WhatsAppCallManager:
    """
    Manages WhatsApp call detection and control via the Node.js bridge.

    Usage:
        mgr = WhatsAppCallManager(on_incoming_call=callback)
        mgr.start()
        ...
        mgr.answer_call(call_id)
        mgr.reject_call(call_id)
        mgr.stop()
    """

    def __init__(
        self,
        on_incoming_call: Optional[Callable] = None,
        on_call_ended: Optional[Callable] = None,
        on_qr: Optional[Callable] = None,
        log_fn: Optional[Callable] = None,
    ):
        self._on_incoming = on_incoming_call
        self._on_ended = on_call_ended
        self._on_qr = on_qr
        self._log = log_fn or (lambda msg: print(f"[WACall] {msg}"))
        self._proc: Optional[subprocess.Popen] = None
        self._polling = False
        self._poll_thread: Optional[threading.Thread] = None
        self._known_calls: dict = {}  # call_id -> entry
        self._desktop_answer_points: dict[str, tuple[int, int]] = {}
        self._connected = False
        self._last_qr = ""
        self._log_thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Start the Node.js bridge process."""
        if not BRIDGE_JS.exists():
            self._log("❌ bridge.js not found — run: cd whatsapp_bridge && npm install")
            return False

        if self._proc and self._proc.poll() is None:
            self._log("Bridge already running")
            return True

        if requests is None:
            self._log("❌ requests is not installed — WhatsApp call bridge is unavailable")
            return False

        # `sys.executable.replace(...)` only works for a very particular Python
        # installation.  Resolve Node like a normal desktop dependency instead.
        node = (os.environ.get("OPERO_NODE") or shutil.which("node")
                or shutil.which("node.exe"))
        if not node:
            self._log("❌ Node.js was not found. Install Node.js LTS or set OPERO_NODE.")
            return False

        try:
            self._proc = subprocess.Popen(
                [node, str(BRIDGE_JS)],
                cwd=str(BRIDGE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._log(f"🚀 Bridge started (PID {self._proc.pid})")
            # Drain the child pipe continuously.  Leaving it unread can freeze
            # Node once its stdout buffer fills (especially while it prints QR).
            self._log_thread = threading.Thread(target=self._drain_bridge_log, daemon=True)
            self._log_thread.start()
            self._start_polling()
            return True
        except Exception as e:
            self._log(f"❌ Failed to start bridge: {e}")
            return False

    def stop(self):
        """Stop the bridge process."""
        self._polling = False
        if self._poll_thread:
            self._poll_thread.join(timeout=3)
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception as e:
                    log.debug("%s", e)
            self._proc = None
        self._log("🛑 Bridge stopped")

    def _drain_bridge_log(self) -> None:
        proc = self._proc
        if not proc or not proc.stdout:
            return
        try:
            for line in proc.stdout:
                line = line.strip()
                if line and ("connected" in line.lower() or "incoming" in line.lower()
                             or "fatal" in line.lower() or "error" in line.lower()):
                    self._log(f"Bridge: {line}")
        except Exception as e:
            log.debug("%s", e)

    def _start_polling(self):
        """Start polling the bridge for calls in a background thread."""
        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self):
        """Poll the bridge and visible WhatsApp Desktop call surface."""
        while self._polling:
            current_calls = {}
            try:
                resp = requests.get(f"{BRIDGE_URL}/status", timeout=3)
                data = resp.json()
                self._connected = data.get("status") == "connected"

                if data.get("hasQr"):
                    qr = self.get_qr()
                    if qr and qr != self._last_qr:
                        self._last_qr = qr
                        self._log("WhatsApp pairing QR is ready.")
                        if self._on_qr:
                            self._on_qr(qr)
                elif self._last_qr:
                    self._last_qr = ""
                    # A successful link clears the QR; callers use this to
                    # dismiss the pairing panel without waiting for a restart.
                    if self._connected and self._on_qr:
                        self._on_qr("")

                if self._connected:
                    calls_resp = requests.get(f"{BRIDGE_URL}/calls", timeout=3)
                    calls_data = calls_resp.json()
                    current_calls = {c["id"]: c for c in calls_data.get("calls", [])}

            except requests.ConnectionError:
                if self._connected:
                    self._log("⚠️ Bridge connection lost")
                    self._connected = False
            except Exception as e:
                pass  # silently retry

            # whatsapp-web.js is not guaranteed to emit personal-call events.
            # Fall back to the visible Desktop UI: detect the green circular
            # answer control within the WhatsApp window, never the whole screen.
            desktop_call = self._detect_desktop_incoming()
            if desktop_call:
                current_calls[desktop_call["id"]] = desktop_call

            for call_id, call in current_calls.items():
                if call_id not in self._known_calls:
                    self._known_calls[call_id] = call
                    self._log(f"📞 Incoming call detected ({call.get('source', 'bridge')})")
                    if self._on_incoming:
                        try:
                            self._on_incoming(call)
                        except Exception as e:
                            self._log(f"Callback error: {e}")

            for call_id in list(self._known_calls.keys()):
                if call_id not in current_calls:
                    call = self._known_calls.pop(call_id)
                    self._desktop_answer_points.pop(call_id, None)
                    if self._on_ended:
                        try:
                            self._on_ended(call)
                        except Exception as e:
                            self._log(f"Callback error: {e}")

            time.sleep(2)

    def _detect_desktop_incoming(self) -> Optional[dict]:
        """Return a synthetic call when WhatsApp Desktop shows Answer.

        This intentionally analyses only the WhatsApp window and only looks for
        a large, round green answer affordance in its lower centre. It does not
        OCR chats or inspect any other application content.
        """
        if not _HAS_PYAUTOGUI:
            return None
        try:
            import pygetwindow as gw
            windows = [w for w in gw.getAllWindows()
                       if "whatsapp" in (w.title or "").lower() and w.width > 300 and w.height > 300]
            if not windows:
                return None
            win = windows[0]
            image = pyautogui.screenshot(region=(win.left, win.top, win.width, win.height))
            rgb = np.asarray(image.convert("RGB"))
            r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
            mask = ((g >= 115) & (g > r * 1.28) & (g > b * 1.12)).astype(np.uint8)
            try:
                import cv2
                count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
            except Exception:
                return None
            candidates = []
            for i in range(1, count):
                x, y, width, height, area = stats[i]
                cx, cy = centroids[i]
                if (150 <= area <= 18000 and 0.55 <= width / max(height, 1) <= 1.8
                        and win.width * .25 <= cx <= win.width * .75
                        and win.height * .48 <= cy <= win.height * .95):
                    candidates.append((area, int(cx), int(cy)))
            if not candidates:
                return None
            _, cx, cy = max(candidates)
            call_id = "desktop-incoming"
            self._desktop_answer_points[call_id] = (win.left + cx, win.top + cy)
            return {"id": call_id, "from": "WhatsApp caller", "fromName": "WhatsApp caller",
                    "isVideo": False, "timestamp": int(time.time()), "source": "desktop"}
        except Exception:
            return None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_status(self) -> dict:
        """Get bridge status."""
        try:
            resp = requests.get(f"{BRIDGE_URL}/status", timeout=3)
            return resp.json()
        except Exception:
            return {"status": "disconnected"}

    def get_active_calls(self) -> list:
        """Get list of active incoming calls."""
        try:
            resp = requests.get(f"{BRIDGE_URL}/calls", timeout=3)
            return resp.json().get("calls", [])
        except Exception:
            return []

    def get_qr(self) -> str:
        """Return the current WhatsApp Web pairing QR payload, if any."""
        try:
            return str(requests.get(f"{BRIDGE_URL}/qr", timeout=3).json().get("qr") or "")
        except Exception:
            return ""

    def refresh_qr(self) -> bool:
        """Force the bridge to log out and generate a new QR code."""
        try:
            resp = requests.post(f"{BRIDGE_URL}/qr/refresh", timeout=10)
            return resp.json().get("ok", False)
        except Exception:
            return False

    def start_outgoing_call(self, receiver: str, call_type: str = "voice") -> str:
        """Start a desktop WhatsApp call through the supported action layer.

        WhatsApp does not expose a public API for programmatically placing or
        answering personal calls.  The bridge is used for call *detection*;
        the desktop client remains the actual call endpoint.
        """
        from actions.send_message import _whatsapp_call
        return _whatsapp_call(receiver, call_type)

    def answer_call(self, call_id: str) -> bool:
        """
        Answer an incoming call.
        
        Since whatsapp-web.js can't natively answer calls, this:
        1. Marks the call as answered in the bridge
        2. Uses PyAutoGUI to click the answer button in WhatsApp Desktop
        """
        if not _HAS_PYAUTOGUI:
            self._log("❌ PyAutoGUI not installed — cannot answer calls")
            return False

        # Mark in bridge
        try:
            requests.post(f"{BRIDGE_URL}/calls/{call_id}/answer", timeout=3)
        except Exception as e:
            log.debug("%s", e)

        # Try to click answer in WhatsApp Desktop
        self._log("🖱️ Clicking answer button in WhatsApp Desktop...")
        try:
            import pygetwindow as gw
            wa_windows = [w for w in gw.getAllWindows() if "whatsapp" in w.title.lower()]
            if not wa_windows:
                self._log("❌ WhatsApp Desktop not found")
                return False

            wa_win = wa_windows[0]
            wa_win.activate()
            time.sleep(0.5)

            # Get window position and size
            left, top = wa_win.left, wa_win.top
            w, h = wa_win.width, wa_win.height

            # Use the visual detector's exact green-button centre when it
            # found one; retain a conservative fallback for bridge-only calls.
            answer_x, answer_y = self._desktop_answer_points.get(
                call_id, (left + int(w * 0.55), top + int(h * 0.85))
            )

            pyautogui.click(answer_x, answer_y)
            self._log(f"✅ Clicked answer at ({answer_x}, {answer_y})")
            return True

        except Exception as e:
            self._log(f"❌ Failed to click answer: {e}")
            return False

    def reject_call(self, call_id: str) -> bool:
        """Reject an incoming call."""
        if not _HAS_PYAUTOGUI:
            self._log("❌ PyAutoGUI not installed")
            return False

        # Mark in bridge
        try:
            requests.post(f"{BRIDGE_URL}/calls/{call_id}/reject", timeout=3)
        except Exception as e:
            log.debug("%s", e)

        # Try to click reject (red phone) in WhatsApp Desktop
        self._log("🖱️ Clicking reject button...")
        try:
            import pygetwindow as gw
            wa_windows = [w for w in gw.getAllWindows() if "whatsapp" in w.title.lower()]
            if not wa_windows:
                self._log("❌ WhatsApp Desktop not found")
                return False

            wa_win = wa_windows[0]
            wa_win.activate()
            time.sleep(0.5)

            left, top = wa_win.left, wa_win.top
            w, h = wa_win.width, wa_win.height

            # Reject button is typically to the left of answer
            reject_x = left + int(w * 0.45)
            reject_y = top + int(h * 0.85)

            pyautogui.click(reject_x, reject_y)
            self._log(f"✅ Clicked reject at ({reject_x}, {reject_y})")
            return True

        except Exception as e:
            self._log(f"❌ Failed to click reject: {e}")
            return False

    def hangup(self) -> bool:
        """Hang up active call."""
        try:
            requests.post(f"{BRIDGE_URL}/calls/hangup", timeout=3)
            self._log("📞 Call hung up")
            return True
        except Exception:
            return False


# ── Singleton for OPERO ──────────────────────────────────────────────────────
_call_manager: Optional[WhatsAppCallManager] = None


def get_call_manager(
    on_incoming_call: Optional[Callable] = None,
    on_call_ended: Optional[Callable] = None,
    on_qr: Optional[Callable] = None,
    log_fn: Optional[Callable] = None,
) -> WhatsAppCallManager:
    """Get or create the global WhatsApp call manager."""
    global _call_manager
    if _call_manager is None:
        _call_manager = WhatsAppCallManager(
            on_incoming_call=on_incoming_call,
            on_call_ended=on_call_ended,
            on_qr=on_qr,
            log_fn=log_fn,
        )
    return _call_manager
