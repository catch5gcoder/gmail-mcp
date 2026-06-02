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

_services: dict        = {}      # {email: google api service}
_profiles: dict        = {}      # {email: {email, name}}
_active_account: str   = ""      # currently selected account email
_email_cache: dict     = {}      # {(account, message_id): (ts, email_dict)}
_cache_lock            = threading.Lock()
CACHE_TTL              = 300

# SSE push notification state
_subscribers: list[queue.Queue] = []
_sub_lock    = threading.Lock()
_poller_started = False
_poller_lock    = threading.Lock()
POLL_INTERVAL   = 30

PRIORITY_LABELS = ["INBOX", "STARRED", "SENT", "DRAFTS", "SPAM", "TRASH"]
LABEL_ICONS = {
    "INBOX": "📥", "STARRED": "⭐", "SENT": "📤",
    "DRAFTS": "📝", "SPAM": "🚫", "TRASH": "🗑️",
}


def _is_transient(e: Exception) -> bool:
    if isinstance(e, ssl.SSLError):
        return True
    msg = str(e).lower()
    return any(x in msg for x in ("ssl", "wrong version", "connection reset",
                                   "broken pipe", "remote end closed", "eof occurred"))


def _active() -> str:
    """Return the current active account email, defaulting to first available."""
    global _active_account
    if not _active_account:
        accounts = gmail.list_accounts()
        _active_account = accounts[0] if accounts else ""
    return _active_account


def get_service(email: str | None = None) -> object:
    """Return (cached) Gmail service for *email* (defaults to active account)."""
    acct = email or _active()
    if acct not in _services:
        _services[acct] = gmail.get_service(acct)
    return _services[acct]


def get_profile(email: str | None = None) -> dict:
    acct = email or _active()
    if acct not in _profiles:
        _profiles[acct] = gmail.get_profile(get_service(acct))
    return _profiles[acct]


def get_email_cached(message_id: str, email: str | None = None) -> dict:
    acct = email or _active()
    key  = (acct, message_id)
    with _cache_lock:
        entry = _email_cache.get(key)
    if entry:
        ts, data = entry
        if time.time() - ts < CACHE_TTL:
            return data

    for attempt in range(2):
        try:
            data = gmail.get_email(get_service(acct), message_id)
            with _cache_lock:
                _email_cache[key] = (time.time(), data)
            return data
        except Exception as e:
            if attempt == 0 and _is_transient(e):
                _services.pop(acct, None)
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
    """Background thread: check every account's inbox and push new arrivals."""
    last_ids: dict[str, set[str]] = {}   # {account: set of message IDs}

    while True:
        for acct in gmail.list_accounts():
            try:
                emails      = gmail.list_emails(get_service(acct), label_ids=["INBOX"], max_results=15)
                current_ids = {e["id"] for e in emails}
                prev_ids    = last_ids.get(acct)

                if prev_ids is not None:
                    new_ids = current_ids - prev_ids
                    if new_ids:
                        new_emails = [e for e in emails if e["id"] in new_ids]
                        _broadcast({"type": "new_emails", "count": len(new_emails),
                                    "emails": new_emails, "account": acct})

                last_ids[acct] = current_ids
            except Exception as e:
                if _is_transient(e):
                    _services.pop(acct, None)

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


def _list_emails_with_retry(label: str, query: str, acct: str) -> list:
    for attempt in range(2):
        try:
            return gmail.list_emails(
                get_service(acct),
                label_ids=[label] if not query else None,
                max_results=25,
                query=query,
            )
        except Exception as e:
            if attempt == 0 and _is_transient(e):
                _services.pop(acct, None)
                continue
            raise


@app.route("/")
def index():
    global _active_account
    label = request.args.get("label", "INBOX")
    query = request.args.get("q", "")
    acct  = request.args.get("account", "") or _active()
    _active_account = acct
    try:
        emails   = _list_emails_with_retry(label, query, acct)
        sidebar  = _sidebar_labels()
        profile  = get_profile(acct)
        accounts = gmail.list_accounts()
    except Exception as e:
        return (
            f"<h3 style='font-family:Arial;padding:24px;color:#d93025'>"
            f"Could not load inbox: {e}<br><a href='/'>Retry</a></h3>"
        ), 500
    return render_template(
        "inbox.html",
        emails=emails,
        labels=sidebar,
        current_label=label,
        query=query,
        label_icons=LABEL_ICONS,
        user_email=profile["email"],
        accounts=accounts,
        active_account=acct,
    )


# ── Account management ──────────────────────────────────────────────────────

@app.route("/accounts/add", methods=["POST"])
def accounts_add():
    """Blocking: opens browser OAuth, saves token, returns new account email."""
    try:
        email = gmail.add_account()
        _active_account_set(email)
        return jsonify({"ok": True, "email": email})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/accounts/switch/<email>", methods=["POST"])
def accounts_switch(email):
    global _active_account
    if email not in gmail.list_accounts():
        return jsonify({"ok": False, "error": "Unknown account"}), 400
    _active_account = email
    return jsonify({"ok": True})


@app.route("/accounts/remove/<email>", methods=["POST"])
def accounts_remove(email):
    global _active_account
    gmail.remove_account(email)
    _services.pop(email, None)
    _profiles.pop(email, None)
    if _active_account == email:
        remaining = gmail.list_accounts()
        _active_account = remaining[0] if remaining else ""
    return jsonify({"ok": True})


def _active_account_set(email: str) -> None:
    global _active_account
    _active_account = email


@app.route("/email/<message_id>/body")
def email_body(message_id):
    acct = request.args.get("account", "") or _active()
    try:
        email = get_email_cached(message_id, acct)
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
    acct = request.args.get("account", "") or _active()
    try:
        email = get_email_cached(message_id, acct)
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
    acct = request.args.get("account", "") or _active()
    for attempt in range(2):
        try:
            gmail.trash_email(get_service(acct), message_id)
            with _cache_lock:
                _email_cache.pop((acct, message_id), None)
            return jsonify({"ok": True})
        except Exception as e:
            if attempt == 0 and _is_transient(e):
                _services.pop(acct, None)
                continue
            return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/email/<message_id>/untrash", methods=["POST"])
def untrash_email(message_id):
    acct = request.args.get("account", "") or _active()
    for attempt in range(2):
        try:
            gmail.untrash_email(get_service(acct), message_id)
            return jsonify({"ok": True})
        except Exception as e:
            if attempt == 0 and _is_transient(e):
                _services.pop(acct, None)
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
