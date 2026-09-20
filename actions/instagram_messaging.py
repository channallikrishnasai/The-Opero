"""Meta Graph API connector for Instagram professional-account messaging."""
from __future__ import annotations

import json
from pathlib import Path

import requests

from core import confirm

CONFIG = Path(__file__).resolve().parent.parent / "config" / "instagram.json"


def _config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ready(cfg: dict) -> tuple[bool, str]:
    if not cfg.get("access_token") or not cfg.get("account_id"):
        return False, "Instagram is not connected. Configure a Meta Graph access token and professional-account ID in config/instagram.json."
    return True, ""


def _request(method: str, path: str, *, data: dict | None = None) -> dict:
    cfg = _config(); ok, message = _ready(cfg)
    if not ok:
        raise RuntimeError(message)
    version = str(cfg.get("api_version", "v25.0"))
    base_url = str(cfg.get("base_url", "https://graph.instagram.com")).rstrip("/")
    response = requests.request(method, f"{base_url}/{version}/{path.lstrip('/')}", params={"access_token": cfg["access_token"]}, json=data, timeout=20)
    if not response.ok:
        raise RuntimeError(f"Instagram API error {response.status_code}: {response.text[:300]}")
    return response.json()


def _send(recipient_id: str, text: str) -> str:
    cfg = _config()
    _request("POST", f"{cfg['account_id']}/messages", data={"recipient": {"id": recipient_id}, "message": {"text": text}})
    return "Instagram message sent."


def execute(parameters: dict) -> str:
    action = str(parameters.get("action", "status")).strip().lower()
    if action == "status":
        ok, message = _ready(_config())
        return "Instagram professional messaging is connected." if ok else message
    if action == "list":
        cfg = _config()
        result = _request("GET", f"{cfg['account_id']}/conversations")
        conversations = result.get("data", [])
        if not conversations:
            return "No Instagram conversations returned."
        return "\n".join(f"{item.get('id', '')} | {item.get('updated_time', '')}" for item in conversations[:20])
    if action == "read":
        conversation_id = str(parameters.get("conversation_id", "")).strip()
        if not conversation_id:
            return "conversation_id is required."
        result = _request("GET", f"{conversation_id}/messages")
        messages = result.get("data", [])
        if not messages:
            return "No messages returned for that conversation."
        return "\n".join(
            f"{item.get('from', {}).get('id', '')} | {item.get('created_time', '')} | {item.get('message', '')}"
            for item in messages[:50]
        )
    if action == "send":
        recipient_id = str(parameters.get("recipient_id", "")).strip()
        text = str(parameters.get("text", "")).strip()
        if not recipient_id or not text:
            return "recipient_id and text are required."
        return confirm.request("instagram-send", "Send Instagram message", f"Send this message to Instagram recipient {recipient_id}?", lambda: _send(recipient_id, text))
    return "Unknown Instagram action. Use status, list, read, or send."


TOOL = {
    "name": "instagram_messaging",
    "description": "Use a connected Meta Instagram professional account to list supported conversations and send messages after on-screen confirmation.",
    "parameters": {"type": "OBJECT", "properties": {
        "action": {"type": "string", "description": "status | list | read | send"},
        "recipient_id": {"type": "string"}, "conversation_id": {"type": "string"}, "text": {"type": "string"},
    }},
    "handler": execute,
}


