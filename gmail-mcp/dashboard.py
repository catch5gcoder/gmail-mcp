#!/usr/bin/env python3
"""Gmail browser dashboard — Flask web UI over gmail_client.py."""

import json
import queue
import re
import ssl
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).parent))
import gmail_client as gmail

app = Flask(__name__)

_service = None
_profile = None
_email_cache: dict = {}          # {message_id: (timestamp, email_dict)}
_cache_lock = threading.Lock()   # protects concurrent reads/writes to _email_cache
CACHE_TTL = 300

# SSE push notification state
_subscribers: list[queue.Queue] = []   # one Queue per connected browser tab
_sub_lock = threading.Lock()
_poller_started = False
_poller_lock = threading.Lock()
POLL_INTERVAL = 30  # seconds between Gmail inbox checks

PRIORITY_LABELS = ["INBOX", "STARRED", "SENT", "DRAFTS", "SPAM", "TRASH"]
LABEL_ICONS = {
    "INBOX": "📥", "STARRED": "⭐", "SENT": "📤",
    "DRAFTS": "📝", "SPAM": "🚫", "TRASH": "🗑️",
}


def get_service():
    global _service
    if _service is None:
        _service = gmail.get_service()
    return _service


def get_profile():
    global _profile
    if _profile is None:
        _profile = gmail.get_profile(get_service())
    return _profile


def _is_transient(e: Exception) -> bool:
    """True for SSL / stale-connection errors that go away with a fresh connection."""
    if isinstance(e, ssl.SSLError):
        return True
    msg = str(e).lower()
    return any(x in msg for x in ("ssl", "wrong version", "connection reset",
                                   "broken pipe", "remote end closed", "eof occurred"))


def get_email_cached(message_id: str) -> dict:
    global _service
    with _cache_lock:
        entry = _email_cache.get(message_id)
    if entry:
        ts, data = entry
        if time.time() - ts < CACHE_TTL:
            return data

    # Retry once on transient SSL / connection errors
    for attempt in range(2):
        try:
            data = gmail.get_email(get_service(), message_id)
            with _cache_lock:
                _email_cache[message_id] = (time.time(), data)
            return data
        except Exception as e:
            if attempt == 0 and _is_transient(e):
                _service = None   # force a fresh connection next attempt
                continue
            raise


def _broadcast(event: dict) -> None:
    """Push an SSE event to every connected browser tab."""
    with _sub_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


def _poll_for_new_emails() -> None:
    """Background thread: check inbox every POLL_INTERVAL seconds and push new arrivals."""
    global _service
    last_ids: set[str] = set()
    initialized = False

    while True:
        try:
            emails = gmail.list_emails(get_service(), label_ids=["INBOX"], max_results=15)
            current_ids = {e["id"] for e in emails}

            if initialized:
                new_ids = current_ids - last_ids
                if new_ids:
                    new_emails = [e for e in emails if e["id"] in new_ids]
                    _broadcast({"type": "new_emails", "count": len(new_emails), "emails": new_emails})

            last_ids = current_ids
            initialized = True
        except Exception as e:
            if _is_transient(e):
                _service = None  # force reconnect next iteration

        time.sleep(POLL_INTERVAL)


@app.before_request
def _start_poller_once():
    """Start the background polling thread on the very first request."""
    global _poller_started
    if not _poller_started:
        with _poller_lock:
            if not _poller_started:
                _poller_started = True
                t = threading.Thread(target=_poll_for_new_emails, daemon=True, name="gmail-poller")
                t.start()


@app.route("/stream")
def stream():
    """SSE endpoint — browser holds this connection open to receive push events."""
    def generate():
        q: queue.Queue = queue.Queue(maxsize=100)
        with _sub_lock:
            _subscribers.append(q)
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    event = q.get(timeout=25)
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"event: {event['type']}\ndata: {payload}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"   # SSE comment prevents timeout
        except GeneratorExit:
            pass
        finally:
            with _sub_lock:
                try:
                    _subscribers.remove(q)
                except ValueError:
                    pass

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _format_from(from_str: str) -> str:
    m = re.match(r'^"?([^"<]+)"?\s*<', from_str)
    return m.group(1).strip() if m else from_str


def _format_date(date_str: str) -> str:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%d %b %Y %H:%M:%S %z", "%d %b %Y %H:%M:%S %Z"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            now = datetime.now(dt.tzinfo)
            if dt.date() == now.date():
                return dt.strftime("%I:%M %p").lstrip("0")
            if dt.year == now.year:
                return dt.strftime("%b %d").replace(" 0", " ")
            return dt.strftime("%b %d, %Y")
        except ValueError:
            continue
    parts = date_str.split()
    return " ".join(parts[1:4]) if len(parts) >= 4 else date_str


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


app.jinja_env.filters["format_from"] = _format_from
app.jinja_env.filters["format_date"] = _format_date


def _sidebar_labels():
    all_labels = gmail.list_labels(get_service())
    priority = sorted(
        [l for l in all_labels if l["id"] in PRIORITY_LABELS],
        key=lambda l: PRIORITY_LABELS.index(l["id"]),
    )
    user = [l for l in all_labels if l["type"] == "user"]
    return priority + user


def _list_emails_with_retry(label: str, query: str) -> list:
    global _service
    for attempt in range(2):
        try:
            return gmail.list_emails(
                get_service(),
                label_ids=[label] if not query else None,
                max_results=25,
                query=query,
            )
        except Exception as e:
            if attempt == 0 and _is_transient(e):
                _service = None
                continue
            raise


@app.route("/")
def index():
    label = request.args.get("label", "INBOX")
    query = request.args.get("q", "")
    try:
        emails = _list_emails_with_retry(label, query)
        sidebar = _sidebar_labels()
        profile = get_profile()
    except Exception as e:
        return (
            f"<h3 style='font-family:Arial;padding:24px;color:#d93025'>"
            f"Could not load inbox: {e}<br>"
            f"<a href='/'>Retry</a></h3>"
        ), 500
    return render_template(
        "inbox.html",
        emails=emails,
        labels=sidebar,
        current_label=label,
        query=query,
        label_icons=LABEL_ICONS,
        user_email=profile["email"],
    )


@app.route("/email/<message_id>/body")
def email_body(message_id):
    try:
        email = get_email_cached(message_id)
        html = email.get("html_body", "")
        if html:
            if "<head>" in html.lower():
                html = re.sub(r"(<head[^>]*>)", r'\1<base target="_blank">', html, count=1, flags=re.IGNORECASE)
            else:
                html = '<base target="_blank">' + html
        else:
            plain = (email.get("body", "(No content)")
                     .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            html = (
                "<!DOCTYPE html><html><head><base target=\"_blank\"></head><body>"
                f"<pre style=\"font-family:Arial,sans-serif;font-size:14px;"
                f"white-space:pre-wrap;padding:24px;color:#202124;line-height:1.6\">{plain}</pre>"
                "</body></html>"
            )
        return Response(html, mimetype="text/html; charset=utf-8")
    except Exception as e:
        error_html = (
            "<!DOCTYPE html><html><body style=\"font-family:Arial,sans-serif;padding:32px;\">"
            f"<p style=\"color:#d93025;font-size:15px;\">Could not load email body: {e}</p>"
            "<p style=\"color:#5f6368;font-size:13px;\">Try selecting the email again, "
            "or open it directly in Gmail.</p></body></html>"
        )
        return Response(error_html, mimetype="text/html; charset=utf-8", status=200)


@app.route("/email/<message_id>/detail")
def email_detail_json(message_id):
    try:
        email = get_email_cached(message_id)
        attachments = [
            {**att, "size_str": _format_size(att.get("size", 0))}
            for att in email.get("attachments", [])
        ]
        return jsonify({
            "subject": email["subject"],
            "from": email["from"],
            "to": email["to"],
            "cc": email.get("cc", ""),
            "date": email["date"],
            "body": email.get("body", ""),
            "html_body": email.get("html_body", ""),
            "attachments": attachments,
            "labelIds": email.get("labelIds", []),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/email/<message_id>/trash", methods=["POST"])
def trash_email(message_id):
    global _service
    for attempt in range(2):
        try:
            gmail.trash_email(get_service(), message_id)
            with _cache_lock:
                _email_cache.pop(message_id, None)
            return jsonify({"ok": True})
        except Exception as e:
            if attempt == 0 and _is_transient(e):
                _service = None
                continue
            return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/email/<message_id>/untrash", methods=["POST"])
def untrash_email(message_id):
    global _service
    for attempt in range(2):
        try:
            gmail.untrash_email(get_service(), message_id)
            return jsonify({"ok": True})
        except Exception as e:
            if attempt == 0 and _is_transient(e):
                _service = None
                continue
            return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/send", methods=["POST"])
def send():
    data = request.get_json()
    try:
        result = gmail.send_email(
            get_service(),
            to=data["to"],
            subject=data["subject"],
            body=data["body"],
            cc=data.get("cc", ""),
            html=True,
        )
        return jsonify({"ok": True, "id": result["id"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("\n  Gmail Dashboard at http://localhost:5000\n")
    app.run(debug=False, port=5000)
