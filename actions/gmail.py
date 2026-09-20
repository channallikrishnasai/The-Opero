"""Gmail OAuth action. Credentials stay local and sending stays confirmation-gated."""
from __future__ import annotations

import base64
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from core import confirm

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
CLIENT_FILE = CONFIG_DIR / "google_oauth_client.json"
TOKEN_FILE = CONFIG_DIR / "gmail_token.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
]


def _service(interactive: bool = False):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Gmail dependencies are missing. Run: pip install google-api-python-client google-auth-oauthlib") from exc
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES) if TOKEN_FILE.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not interactive:
            raise RuntimeError("Gmail is not connected. Use action=connect first.")
        if not CLIENT_FILE.is_file():
            raise RuntimeError("Missing config/google_oauth_client.json. Create a Google OAuth Desktop client and save its JSON there.")
        creds = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES).run_local_server(port=0)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    return {str(h.get("name", "")).lower(): str(h.get("value", "")) for h in payload.get("headers", [])}


def _message_body(payload: dict[str, Any]) -> str:
    data = payload.get("body", {}).get("data")
    if data:
        return base64.urlsafe_b64decode(data + "===").decode("utf-8", "replace")
    for part in payload.get("parts", []):
        text = _message_body(part)
        if text:
            return text
    return ""


def _send(service, to: str, subject: str, body: str) -> str:
    msg = MIMEText(body, "plain", "utf-8")
    msg["to"] = to
    msg["subject"] = subject
    service.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).execute()
    return f"Email sent to {to}."


def execute(parameters: dict) -> str:
    action = str(parameters.get("action", "status")).strip().lower()
    if action == "status":
        from actions.google_workspace_mcp import get_stored_gmail_credentials
        addr, pw = get_stored_gmail_credentials()
        if addr and pw:
            return f"Gmail is connected via App Passcode ({addr})."
        return ("Gmail is connected via OAuth." if TOKEN_FILE.is_file()
                else "Gmail is not connected. Easiest fix: action=connect_app_passcode with "
                     "your Gmail address and a 16-character App Password from "
                     "https://myaccount.google.com/apppasswords (or action=connect for OAuth).")
    if action in ("connect_app_passcode", "save_passcode"):
        email_addr = str(parameters.get("email", "")).strip()
        app_password = str(parameters.get("password", "") or parameters.get("app_password", "")).strip()
        if not email_addr or not app_password:
            return "Both the Gmail address and its App Password are required."
        from actions.google_workspace_mcp import save_stored_gmail_credentials, GmailEngine
        if not save_stored_gmail_credentials(email_addr, app_password):
            return "Could not save the Gmail credentials (the local credential store is unavailable)."
        # Verify immediately: a saved-but-invalid password looks identical to a
        # working one until the first search fails.
        res = GmailEngine.test_connection()
        if res.get("success"):
            return f"Gmail connected as {email_addr}. {res.get('message', '')}"
        return f"Saved, but Gmail refused the sign-in: {res.get('message', '')}"
    if action == "connect":
        _service(interactive=True)
        return "Gmail connected securely through Google OAuth."
    if action == "disconnect":
        def _disconnect() -> str:
            removed = []
            if TOKEN_FILE.is_file():
                TOKEN_FILE.unlink()
                removed.append("OAuth token")
            from actions.google_workspace_mcp import EMAIL_CREDENTIALS_FILE
            if EMAIL_CREDENTIALS_FILE.exists():
                EMAIL_CREDENTIALS_FILE.unlink()
                removed.append("App Passcode credentials")
            if removed:
                if removed == ["OAuth token"]:
                    return "Local Gmail OAuth token removed."
                return f"Removed Gmail connections ({', '.join(removed)})."
            return "Gmail is already disconnected on this device."
        return confirm.request("gmail-disconnect", "Disconnect Gmail", "Remove Gmail credentials from this device?", _disconnect)
    if action == "search":
        query = str(parameters.get("query", "")).strip()
        limit = max(1, min(20, int(parameters.get("limit", 10))))
        from actions.google_workspace_mcp import get_stored_gmail_credentials, GmailEngine
        addr, pw = get_stored_gmail_credentials()
        if addr and pw:
            return GmailEngine.list_messages(query=query or "ALL", max_results=limit)
        service = _service()
        found = service.users().messages().list(userId="me", q=query, maxResults=limit).execute().get("messages", [])
        items = []
        for item in found:
            msg = service.users().messages().get(userId="me", id=item["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]).execute()
            h = _headers(msg.get("payload", {}))
            items.append(f"{item['id']} | {h.get('from', '')} | {h.get('subject', '(no subject)')} | {h.get('date', '')}")
        return "No matching email found." if not items else "\n".join(items)
    if action == "read":
        message_id = str(parameters.get("message_id", "")).strip()
        if not message_id:
            return "message_id is required."
        from actions.google_workspace_mcp import get_stored_gmail_credentials, GmailEngine
        addr, pw = get_stored_gmail_credentials()
        if addr and pw:
            return GmailEngine.read_message(message_id)
        service = _service()
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        h = _headers(msg.get("payload", {}))
        return f"From: {h.get('from', '')}\nSubject: {h.get('subject', '')}\n\n{_message_body(msg.get('payload', {}))[:12000]}"
    if action not in {"draft", "send"}:
        return "Unknown Gmail action. Use status, connect, connect_app_passcode, disconnect, search, read, draft, or send."
    to, subject, body = (str(parameters.get(key, "")).strip() for key in ("to", "subject", "body"))
    if not to or not subject or not body:
        return "to, subject, and body are required."
    from actions.google_workspace_mcp import get_stored_gmail_credentials, GmailEngine
    addr, pw = get_stored_gmail_credentials()
    if addr and pw:
        if action == "draft":
            # IMAP APPEND puts the message in Gmail's own Drafts folder, so a
            # draft saved here is the same draft the user sees in their inbox.
            return confirm.request("gmail-draft", "Save draft",
                                   f"Save a draft of '{subject}' to {to}?",
                                   lambda: GmailEngine.save_draft(to, subject, body))
        return confirm.request("gmail-send", "Send email", f"Send '{subject}' to {to}?", lambda: GmailEngine.send_message(to, subject, body))
    service = _service()
    if action == "draft":
        msg = MIMEText(body, "plain", "utf-8")
        msg["to"] = to
        msg["subject"] = subject
        service.users().drafts().create(userId="me", body={"message": {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}}).execute()
        return f"Draft saved for {to}."
    return confirm.request("gmail-send", "Send email", f"Send '{subject}' to {to}?", lambda: _send(service, to, subject, body))

TOOL = {
    "name": "gmail",
    "description": "Connect Gmail with OAuth or App Passcode, search/read email, save drafts, and send after confirmation.",
    "parameters": {"type": "OBJECT", "properties": {
        "action": {"type": "string", "description": "status | connect | connect_app_passcode | disconnect | search | read | draft | send"},
        "query": {"type": "string"}, "message_id": {"type": "string"}, "limit": {"type": "integer"},
        "to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"},
        "email": {"type": "string"}, "password": {"type": "string"},
    }},
    "handler": execute,
}
