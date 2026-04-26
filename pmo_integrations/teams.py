"""Microsoft Teams notifier — posts Adaptive Cards to an Incoming Webhook.

Hook this from any docevent.  The webhook URL and on/off toggles live in the
"PMO Integration Settings" (Single) doctype.

Best practice references:
  * Teams Incoming Webhooks accept JSON with `type=message` + `attachments`
    containing an Adaptive Card 1.4 payload.
  * Calls are non-blocking via `frappe.enqueue` so we never block document save.
"""
from __future__ import annotations

import json
from typing import Any

import frappe
import requests
from frappe.utils import get_url, getdate, now_datetime


SETTINGS_DT = "PMO Integration Settings"


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def _settings():
    if not frappe.db.exists("DocType", SETTINGS_DT):
        return None
    return frappe.get_cached_doc(SETTINGS_DT)


def _enabled(flag: str) -> bool:
    s = _settings()
    return bool(s and getattr(s, "enabled", 0) and getattr(s, flag, 0))


def _webhook_url() -> str | None:
    s = _settings()
    if not s or not s.enabled:
        return None
    url = (s.teams_webhook_url or "").strip()
    return url or None


# ---------------------------------------------------------------------------
# Adaptive card builder
# ---------------------------------------------------------------------------

def _adaptive_card(title: str, subtitle: str, facts: list[tuple[str, str]],
                   open_url: str | None = None, color: str = "good") -> dict:
    body: list[dict[str, Any]] = [
        {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium",
         "color": color, "wrap": True},
    ]
    if subtitle:
        body.append({"type": "TextBlock", "text": subtitle, "isSubtle": True, "wrap": True})
    if facts:
        body.append({"type": "FactSet",
                     "facts": [{"title": k, "value": v} for k, v in facts]})

    actions: list[dict[str, Any]] = []
    if open_url:
        actions.append({"type": "Action.OpenUrl", "title": "Open in ERPNext", "url": open_url})

    card: dict[str, Any] = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
    }
    if actions:
        card["actions"] = actions

    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": card,
        }],
    }


# ---------------------------------------------------------------------------
# Public sender (always async)
# ---------------------------------------------------------------------------

def _send(payload: dict):
    url = _webhook_url()
    if not url:
        return
    try:
        r = requests.post(url, json=payload, timeout=8)
        if r.status_code >= 300:
            frappe.log_error(f"Teams webhook {r.status_code}: {r.text[:500]}",
                             "PMO Teams Notify")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "PMO Teams Notify")


def _enqueue(payload: dict):
    frappe.enqueue("isc_pmo.pmo_integrations.teams._send",
                   queue="short", payload=payload, now=False)


def _doc_url(doctype: str, name: str) -> str:
    base = (get_url() or "").rstrip("/")
    return f"{base}/app/{doctype.lower().replace(' ', '-')}/{name}"


# ---------------------------------------------------------------------------
# Document-event handlers (referenced from hooks.py)
# ---------------------------------------------------------------------------

def on_todo_after_insert(doc, method=None):
    """Fired when a ToDo is auto-created on a doc assignment.

    ToDo is the canonical "assigned to" trigger across Frappe — Tasks,
    Projects, RAID Items etc all go through it.
    """
    if not _enabled("notify_assignments"):
        return
    if not doc.allocated_to:
        return
    user = frappe.db.get_value("User", doc.allocated_to,
                               ["full_name", "email"], as_dict=True) or {}
    facts = [
        ("Document", f"{doc.reference_type}: {doc.reference_name}"),
        ("Assignee", user.get("full_name") or doc.allocated_to),
        ("Priority", doc.priority or "Medium"),
        ("Due", str(getdate(doc.date)) if doc.date else "—"),
    ]
    payload = _adaptive_card(
        title=f"📋 New assignment — {doc.reference_type}",
        subtitle=(doc.description or "")[:300],
        facts=facts,
        open_url=_doc_url(doc.reference_type, doc.reference_name),
        color="accent",
    )
    _enqueue(payload)


def on_task_update(doc, method=None):
    if not _enabled("notify_task_updates"):
        return
    # Only notify on meaningful changes
    before = doc.get_doc_before_save()
    if before:
        changed = False
        for f in ("status", "progress", "exp_end_date", "priority"):
            if getattr(before, f, None) != getattr(doc, f, None):
                changed = True
                break
        if not changed:
            return
    facts = [
        ("Project", doc.project or "—"),
        ("Status", doc.status or "—"),
        ("Progress", f"{doc.progress or 0}%"),
        ("Due", str(getdate(doc.exp_end_date)) if doc.exp_end_date else "—"),
    ]
    payload = _adaptive_card(
        title=f"🛠 Task updated — {doc.subject}",
        subtitle=(doc.description or "")[:300],
        facts=facts,
        open_url=_doc_url("Task", doc.name),
        color="warning" if doc.status in ("Overdue", "Cancelled") else "good",
    )
    _enqueue(payload)


def on_status_report_submit(doc, method=None):
    if not _enabled("notify_status_reports"):
        return
    facts = [
        ("Project", doc.project or "—"),
        ("Schedule RAG", doc.schedule_rag or "—"),
        ("Cost RAG", doc.cost_rag or "—"),
        ("% Complete", f"{doc.percent_complete or 0}%"),
        ("Reported by", doc.owner),
    ]
    payload = _adaptive_card(
        title=f"📈 Weekly status — {doc.project}",
        subtitle=(doc.highlights or "")[:300],
        facts=facts,
        open_url=_doc_url("Status Report", doc.name),
        color="good",
    )
    _enqueue(payload)


def on_registration_workflow(doc, method=None):
    if not _enabled("notify_registrations"):
        return
    facts = [
        ("State", doc.workflow_state or "—"),
        ("Sponsor", doc.sponsor or "—"),
        ("Portfolio", doc.portfolio or "—"),
        ("Program", doc.program or "—"),
    ]
    payload = _adaptive_card(
        title=f"🧭 Project Registration — {doc.title or doc.name}",
        subtitle=(doc.description or "")[:300],
        facts=facts,
        open_url=_doc_url("Project Registration", doc.name),
        color="accent",
    )
    _enqueue(payload)


def on_kr_checkin(doc, method=None):
    if not _enabled("notify_okr_checkins"):
        return
    facts = [
        ("Key Result", doc.key_result or "—"),
        ("Current Value", str(doc.current_value)),
        ("Confidence", f"{doc.confidence or 0}%"),
    ]
    payload = _adaptive_card(
        title="🎯 OKR check-in",
        subtitle=(doc.message or "")[:300],
        facts=facts,
        open_url=_doc_url("KR Check In", doc.name),
        color="good",
    )
    _enqueue(payload)


# ---------------------------------------------------------------------------
# Manual smoke test (whitelisted)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def send_test_message():
    """Click test from PMO Integration Settings → Test."""
    payload = _adaptive_card(
        title="✅ ISC PMO Autopilot — Teams test",
        subtitle="If you see this card, the webhook is wired correctly.",
        facts=[("Site", get_url()), ("Time", str(now_datetime()))],
        color="good",
    )
    _send(payload)
    return {"ok": True}
