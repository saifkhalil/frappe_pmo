"""Microsoft Graph integration — Outlook calendar two-way push for Tasks.

Flow
====
1. Admin fills `PMO MS365 Settings` (tenant, client_id, client_secret, redirect URI).
2. Each user clicks **Connect Outlook** → redirected to Microsoft consent →
   Microsoft redirects back to `oauth_callback` with an authorization code.
3. We exchange the code for access + refresh tokens, store them in
   `MS Graph Token` (one row per user).
4. On Task save (assigned to that user), we create or patch a calendar event
   in their default Outlook calendar via Graph.

Required Azure AD delegated scopes:
    openid profile email offline_access User.Read Calendars.ReadWrite
"""
from __future__ import annotations

import json
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

import frappe
import requests
from frappe.utils import add_to_date, get_datetime, get_url, now_datetime


SCOPES = "openid profile email offline_access User.Read Calendars.ReadWrite"
GRAPH = "https://graph.microsoft.com/v1.0"


# ---------------------------------------------------------------------------
# Settings + low-level token I/O
# ---------------------------------------------------------------------------

def _settings():
    s = frappe.get_cached_doc("PMO MS365 Settings")
    if not s.enabled:
        frappe.throw("Microsoft 365 integration is disabled in PMO MS365 Settings.")
    if not (s.tenant_id and s.client_id):
        frappe.throw("PMO MS365 Settings is missing tenant_id / client_id.")
    return s


def _redirect_uri(s) -> str:
    if s.redirect_uri:
        return s.redirect_uri
    base = (get_url() or "").rstrip("/")
    return f"{base}/api/method/isc_pmo.pmo_integrations.ms_graph.oauth_callback"


def _token_endpoint(tenant_id: str) -> str:
    return f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


def _authorize_endpoint(tenant_id: str) -> str:
    return f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"


def _get_token_doc(user: str | None = None):
    user = user or frappe.session.user
    if not frappe.db.exists("MS Graph Token", user):
        return None
    return frappe.get_doc("MS Graph Token", user)


def _save_tokens(user: str, payload: dict, tenant_id: str):
    name = user
    if frappe.db.exists("MS Graph Token", name):
        d = frappe.get_doc("MS Graph Token", name)
    else:
        d = frappe.new_doc("MS Graph Token")
        d.user = user
    d.tenant_id = tenant_id
    d.scope = payload.get("scope") or SCOPES
    d.access_token = payload.get("access_token") or ""
    if payload.get("refresh_token"):
        d.refresh_token = payload["refresh_token"]
    expires_in = int(payload.get("expires_in") or 3000)
    d.expires_at = add_to_date(now_datetime(), seconds=expires_in - 60)
    d.flags.ignore_permissions = True
    d.save(ignore_permissions=True)
    frappe.db.commit()


def _get_access_token(user: str | None = None) -> str:
    """Return a valid access token, refreshing if expired."""
    user = user or frappe.session.user
    d = _get_token_doc(user)
    if not d:
        frappe.throw(f"User {user} has not connected Outlook yet.")

    if d.expires_at and get_datetime(d.expires_at) > now_datetime():
        return d.access_token

    # Refresh
    s = _settings()
    refresh_token = d.get_password("refresh_token")
    if not refresh_token:
        frappe.throw(f"Missing refresh token for {user}; please reconnect Outlook.")

    resp = requests.post(_token_endpoint(d.tenant_id or s.tenant_id), data={
        "client_id": s.client_id,
        "client_secret": s.get_password("client_secret"),
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": SCOPES,
    }, timeout=15)
    if resp.status_code >= 300:
        frappe.log_error(f"MS Graph refresh failed: {resp.status_code} {resp.text[:500]}",
                         "PMO Outlook")
        frappe.throw("Could not refresh Outlook token; please reconnect.")
    payload = resp.json()
    _save_tokens(user, payload, d.tenant_id or s.tenant_id)
    return payload["access_token"]


# ---------------------------------------------------------------------------
# OAuth — start + callback
# ---------------------------------------------------------------------------

@frappe.whitelist()
def connect_outlook():
    """Start the per-user OAuth flow.  Returns an authorize URL the client opens."""
    if frappe.session.user == "Guest":
        frappe.throw("Login required.")
    s = _settings()
    state_token = secrets.token_urlsafe(24)
    frappe.cache().set_value(f"pmo_msoauth_state::{state_token}", frappe.session.user, expires_in_sec=900)

    params = {
        "client_id": s.client_id,
        "response_type": "code",
        "redirect_uri": _redirect_uri(s),
        "response_mode": "query",
        "scope": SCOPES,
        "state": state_token,
        "prompt": "select_account",
    }
    url = f"{_authorize_endpoint(s.tenant_id)}?{urllib.parse.urlencode(params)}"
    return {"url": url}


@frappe.whitelist(allow_guest=True)
def oauth_callback(code: str | None = None, state: str | None = None,
                   error: str | None = None, error_description: str | None = None):
    """Microsoft redirects here.  Resolve user from the cached state, exchange code."""
    if error:
        frappe.respond_as_web_page("Outlook connection failed",
                                   f"<p>{error}: {error_description or ''}</p>", indicator_color="red")
        return
    if not (code and state):
        frappe.respond_as_web_page("Outlook connection failed",
                                   "<p>Missing code or state.</p>", indicator_color="red")
        return

    user = frappe.cache().get_value(f"pmo_msoauth_state::{state}")
    if not user:
        frappe.respond_as_web_page("Outlook connection failed",
                                   "<p>State expired; please retry.</p>", indicator_color="red")
        return
    frappe.cache().delete_value(f"pmo_msoauth_state::{state}")

    s = frappe.get_doc("PMO MS365 Settings")
    resp = requests.post(_token_endpoint(s.tenant_id), data={
        "client_id": s.client_id,
        "client_secret": s.get_password("client_secret"),
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": _redirect_uri(s),
        "scope": SCOPES,
    }, timeout=15)
    if resp.status_code >= 300:
        frappe.log_error(f"Code exchange failed: {resp.status_code} {resp.text[:500]}",
                         "PMO Outlook OAuth")
        frappe.respond_as_web_page("Outlook connection failed",
                                   f"<p>{resp.text}</p>", indicator_color="red")
        return

    _save_tokens(user, resp.json(), s.tenant_id)
    frappe.respond_as_web_page(
        "Outlook connected",
        f"<p>Outlook calendar is now linked for <b>{frappe.utils.escape_html(user)}</b>. You can close this tab.</p>",
        indicator_color="green",
    )


@frappe.whitelist()
def disconnect_outlook():
    user = frappe.session.user
    if frappe.db.exists("MS Graph Token", user):
        frappe.delete_doc("MS Graph Token", user, ignore_permissions=True)
        frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def my_status():
    user = frappe.session.user
    d = _get_token_doc(user)
    if not d:
        return {"connected": False}
    return {
        "connected": True,
        "expires_at": str(d.expires_at) if d.expires_at else None,
        "scope": d.scope,
    }


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------

def _graph_request(method: str, path: str, user: str, json_body: dict | None = None) -> dict:
    token = _get_access_token(user)
    url = path if path.startswith("http") else f"{GRAPH}{path}"
    r = requests.request(method, url,
                         headers={"Authorization": f"Bearer {token}",
                                  "Content-Type": "application/json"},
                         json=json_body, timeout=15)
    if r.status_code == 404:
        return {}
    if r.status_code >= 300:
        frappe.log_error(f"Graph {method} {path} {r.status_code}: {r.text[:600]}",
                         "PMO Outlook")
        return {}
    return r.json() if r.text else {}


def _to_graph_dt(value) -> str | None:
    if not value:
        return None
    dt = get_datetime(value)
    # Treat naive as local; Frappe stores TZ-naive datetimes — mark UTC for Graph
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0000000")


# ---------------------------------------------------------------------------
# Task → Outlook event sync
# ---------------------------------------------------------------------------

EVENT_ID_FIELD = "outlook_event_id"  # custom field on Task (added by install)


def _build_task_event(task) -> dict:
    s = frappe.get_cached_doc("PMO MS365 Settings")
    start = task.exp_start_date or task.exp_end_date
    end = task.exp_end_date or task.exp_start_date
    body = {
        "subject": f"[Task] {task.subject}",
        "body": {
            "contentType": "HTML",
            "content": (task.description or "") +
                       f"<br/><br/><b>Project:</b> {task.project or '—'} | <b>Status:</b> {task.status} | <b>Progress:</b> {task.progress or 0}%"
                       f"<br/><a href='{get_url()}/app/task/{task.name}'>Open in ERPNext</a>",
        },
        "showAs": "tentative",
        "isReminderOn": True,
        "reminderMinutesBeforeStart": int(s.default_event_reminder_minutes or 30),
        "categories": ["ISC PMO"],
    }
    # All-day if dates only (no time)
    if start and len(str(start)) <= 10:
        body["isAllDay"] = True
        body["start"] = {"dateTime": f"{start}T00:00:00.0000000", "timeZone": "UTC"}
        body["end"] = {"dateTime": f"{end}T00:00:00.0000000", "timeZone": "UTC"}
    else:
        body["start"] = {"dateTime": _to_graph_dt(start), "timeZone": "UTC"}
        body["end"] = {"dateTime": _to_graph_dt(end), "timeZone": "UTC"}
    return body


def sync_task_event(task_name: str, user: str):
    """Create or update the Outlook calendar event for one Task + assignee."""
    if not frappe.db.exists("MS Graph Token", user):
        return  # user hasn't connected — silently skip
    task = frappe.get_doc("Task", task_name)
    if not (task.exp_start_date or task.exp_end_date):
        return  # nothing to put on a calendar
    if task.status in ("Cancelled", "Completed"):
        # Delete existing event if any
        evt_id = task.get(EVENT_ID_FIELD)
        if evt_id:
            _graph_request("DELETE", f"/me/events/{evt_id}", user)
            frappe.db.set_value("Task", task_name, EVENT_ID_FIELD, None,
                                update_modified=False)
        return

    payload = _build_task_event(task)
    evt_id = task.get(EVENT_ID_FIELD)
    if evt_id:
        _graph_request("PATCH", f"/me/events/{evt_id}", user, payload)
    else:
        created = _graph_request("POST", "/me/events", user, payload)
        new_id = (created or {}).get("id")
        if new_id:
            frappe.db.set_value("Task", task_name, EVENT_ID_FIELD, new_id,
                                update_modified=False)


# ---------------------------------------------------------------------------
# Hook entrypoints (referenced from hooks.py)
# ---------------------------------------------------------------------------

def _is_enabled() -> bool:
    try:
        s = frappe.get_cached_doc("PMO MS365 Settings")
    except Exception:
        return False
    return bool(s.enabled and s.sync_tasks_to_outlook)


def on_task_saved(doc, method=None):
    if not _is_enabled():
        return
    # Sync to every assignee that has connected Outlook
    assignees = frappe.get_all("ToDo",
                               filters={"reference_type": "Task",
                                        "reference_name": doc.name,
                                        "status": "Open"},
                               pluck="allocated_to") or []
    for u in set(assignees):
        if frappe.db.exists("MS Graph Token", u):
            frappe.enqueue("isc_pmo.pmo_integrations.ms_graph.sync_task_event",
                           queue="short", task_name=doc.name, user=u, now=False)


def on_todo_assigned(doc, method=None):
    """When a ToDo is created against a Task, sync that task to the assignee."""
    if not _is_enabled():
        return
    if doc.reference_type != "Task" or not doc.allocated_to:
        return
    if not frappe.db.exists("MS Graph Token", doc.allocated_to):
        return
    frappe.enqueue("isc_pmo.pmo_integrations.ms_graph.sync_task_event",
                   queue="short", task_name=doc.reference_name,
                   user=doc.allocated_to, now=False)


def on_task_trash(doc, method=None):
    if not _is_enabled():
        return
    evt_id = doc.get(EVENT_ID_FIELD)
    if not evt_id:
        return
    assignees = frappe.get_all("ToDo",
                               filters={"reference_type": "Task",
                                        "reference_name": doc.name},
                               pluck="allocated_to") or []
    for u in set(assignees):
        if frappe.db.exists("MS Graph Token", u):
            try:
                _graph_request("DELETE", f"/me/events/{evt_id}", u)
            except Exception:
                pass
