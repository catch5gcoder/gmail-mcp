import base64
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.labels",
]

TOKEN_FILE = Path(__file__).parent / "token.json"
CREDENTIALS_FILE = Path(__file__).parent / "creds.json"


def get_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    "credentials.json not found. Download it from Google Cloud Console "
                    "(APIs & Services > Credentials > OAuth 2.0 Client IDs)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _b64decode(data: str) -> bytes:
    """Base64-decode a Gmail API payload string with correct padding."""
    padding = (4 - len(data) % 4) % 4
    return base64.urlsafe_b64decode(data + "=" * padding)


def _decode_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        try:
            return _b64decode(data).decode("utf-8", errors="replace") if data else ""
        except Exception:
            return ""
    if mime.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _decode_body(part)
            if text:
                return text
    return ""


def _decode_html_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        try:
            return _b64decode(data).decode("utf-8", errors="replace") if data else ""
        except Exception:
            return ""
    if mime.startswith("multipart/"):
        for part in payload.get("parts", []):
            html = _decode_html_body(part)
            if html:
                return html
    return ""


def list_emails(service, label_ids: list[str] | None = None, max_results: int = 10, query: str = "") -> list[dict]:
    params: dict = {"userId": "me", "maxResults": max_results}
    if label_ids:
        params["labelIds"] = label_ids
    if query:
        params["q"] = query
    response = service.users().messages().list(**params).execute()
    messages = response.get("messages", [])
    results = []
    for msg in messages:
        meta = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["Subject", "From", "To", "Date"]
        ).execute()
        headers = {h["name"]: h["value"] for h in meta.get("payload", {}).get("headers", [])}
        results.append({
            "id": msg["id"],
            "threadId": msg.get("threadId"),
            "subject": headers.get("Subject", "(no subject)"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "snippet": meta.get("snippet", ""),
            "labelIds": meta.get("labelIds", []),
        })
    return results


def _extract_attachments(payload: dict) -> list[dict]:
    results = []
    filename = payload.get("filename", "")
    body = payload.get("body", {})
    if filename and body.get("attachmentId"):
        results.append({
            "filename": filename,
            "mimeType": payload.get("mimeType", "application/octet-stream"),
            "size": body.get("size", 0),
        })
    for part in payload.get("parts", []):
        results.extend(_extract_attachments(part))
    return results


def get_profile(service) -> dict:
    profile = service.users().getProfile(userId="me").execute()
    return {
        "email": profile.get("emailAddress", ""),
        "name": profile.get("displayName", ""),
    }


def get_email(service, message_id: str) -> dict:
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = msg.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    body = _decode_body(payload)
    html_body = _decode_html_body(payload)
    return {
        "id": msg["id"],
        "threadId": msg.get("threadId"),
        "subject": headers.get("Subject", "(no subject)"),
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "cc": headers.get("Cc", ""),
        "date": headers.get("Date", ""),
        "body": body,
        "html_body": html_body,
        "snippet": msg.get("snippet", ""),
        "labelIds": msg.get("labelIds", []),
        "attachments": _extract_attachments(payload),
    }


def get_thread(service, thread_id: str) -> list[dict]:
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    return [get_email(service, m["id"]) for m in thread.get("messages", [])]


def list_labels(service) -> list[dict]:
    response = service.users().labels().list(userId="me").execute()
    return [
        {"id": lbl["id"], "name": lbl["name"], "type": lbl.get("type", "")}
        for lbl in response.get("labels", [])
    ]


def send_email(service, to: str, subject: str, body: str, cc: str = "", html: bool = False) -> dict:
    if html:
        mime_msg = MIMEMultipart("alternative")
        mime_msg.attach(MIMEText(body, "html"))
    else:
        mime_msg = MIMEText(body, "plain")
    mime_msg["to"] = to
    mime_msg["subject"] = subject
    if cc:
        mime_msg["cc"] = cc
    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"id": sent["id"], "threadId": sent.get("threadId")}
