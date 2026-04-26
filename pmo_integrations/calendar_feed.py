"""ICS calendar feed for Tasks & Project milestones.

Endpoint:
    /api/method/isc_pmo.pmo_integrations.calendar_feed.feed?token=<personal_token>

The token is the "calendar_token" field on User (auto-generated).  The user
copies the URL into Outlook / Google / Apple Calendar as a *subscribed*
calendar — events refresh automatically (typical refresh: 1×/hour).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

import frappe
from frappe.utils import get_datetime, getdate, get_url


def _ics_escape(text: str) -> str:
    if text is None:
        return ""
    return (str(text)
            .replace("\\", "\\\\").replace(",", "\\,")
            .replace(";", "\\;").replace("\n", "\\n"))


def _fmt_date(d) -> str:
    if not d:
        return ""
    if isinstance(d, str):
        try:
            d = get_datetime(d)
        except Exception:
            return ""
    if isinstance(d, datetime):
        return d.strftime("%Y%m%dT%H%M%SZ")
    return d.strftime("%Y%m%d")


def _vevent(uid: str, summary: str, start, end, description: str = "",
            url: str = "", all_day: bool = True) -> list[str]:
    lines = ["BEGIN:VEVENT", f"UID:{uid}@isc-pmo"]
    if all_day:
        lines.append(f"DTSTART;VALUE=DATE:{getdate(start).strftime('%Y%m%d')}")
        if end:
            # iCal end is exclusive — add 1 day for visual end
            end_d = getdate(end) + timedelta(days=1)
            lines.append(f"DTEND;VALUE=DATE:{end_d.strftime('%Y%m%d')}")
    else:
        lines.append(f"DTSTART:{_fmt_date(start)}")
        if end:
            lines.append(f"DTEND:{_fmt_date(end)}")
    lines.append(f"SUMMARY:{_ics_escape(summary)}")
    if description:
        lines.append(f"DESCRIPTION:{_ics_escape(description)}")
    if url:
        lines.append(f"URL:{url}")
    lines.append(f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}")
    lines.append("END:VEVENT")
    return lines


def _events_for_user(user: str) -> Iterable[list[str]]:
    base = (get_url() or "").rstrip("/")

    # 1. Tasks assigned to the user (via ToDo) ----------------------------
    todo_tasks = frappe.db.sql("""
        SELECT t.name, t.subject, t.description, t.exp_start_date,
               t.exp_end_date, t.status, t.project
        FROM `tabToDo` td
        JOIN `tabTask` t ON t.name = td.reference_name
        WHERE td.reference_type = 'Task' AND td.allocated_to = %s
          AND t.status NOT IN ('Cancelled', 'Completed')
    """, user, as_dict=True)
    for r in todo_tasks:
        if not (r.exp_start_date or r.exp_end_date):
            continue
        yield _vevent(
            uid=f"task-{r.name}",
            summary=f"[Task] {r.subject}",
            start=r.exp_start_date or r.exp_end_date,
            end=r.exp_end_date or r.exp_start_date,
            description=(r.description or "") + f"\\nProject: {r.project or '—'} | Status: {r.status}",
            url=f"{base}/app/task/{r.name}",
        )

    # 2. Projects where the user is a Project User (team member) ---------
    proj = frappe.db.sql("""
        SELECT p.name, p.project_name, p.expected_start_date,
               p.expected_end_date, p.status
        FROM `tabProject User` u
        JOIN `tabProject` p ON p.name = u.parent
        WHERE u.user = %s AND p.is_active = 'Yes'
    """, user, as_dict=True)
    for r in proj:
        if not (r.expected_start_date or r.expected_end_date):
            continue
        yield _vevent(
            uid=f"project-{r.name}",
            summary=f"[Project] {r.project_name}",
            start=r.expected_start_date or r.expected_end_date,
            end=r.expected_end_date or r.expected_start_date,
            description=f"Status: {r.status}",
            url=f"{base}/app/project/{r.name}",
        )

    # 3. KR Check-in due today (for OKR Owners) ---------------------------
    krs = frappe.db.sql("""
        SELECT name, kr_name, target_date FROM `tabKey Result`
        WHERE owner_user = %s AND target_date IS NOT NULL
    """, user, as_dict=True)
    for r in krs:
        yield _vevent(
            uid=f"kr-{r.name}",
            summary=f"[KR Target] {r.kr_name}",
            start=r.target_date,
            end=r.target_date,
            description="Key Result target date",
            url=f"{base}/app/key-result/{r.name}",
        )


@frappe.whitelist(allow_guest=True)
def feed(token: str | None = None):
    """Return an iCalendar feed for the user matching the token."""
    if not token:
        frappe.throw("Missing token")

    user = frappe.db.get_value("User", {"calendar_token": token}, "name")
    if not user:
        frappe.throw("Invalid token", frappe.PermissionError)

    # Switch session to the resolved user so permissions apply correctly.
    frappe.set_user(user)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ISC PMO Autopilot//Calendar Feed//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:ISC PMO — {user}",
        "X-WR-TIMEZONE:UTC",
    ]
    for ev in _events_for_user(user):
        lines.extend(ev)
    lines.append("END:VCALENDAR")

    body = "\r\n".join(lines) + "\r\n"
    frappe.local.response.filename = "isc-pmo.ics"
    frappe.local.response.filecontent = body
    frappe.local.response.type = "binary"
    frappe.local.response.headers = {
        "Content-Type": "text/calendar; charset=utf-8",
        "Content-Disposition": "inline; filename=isc-pmo.ics",
    }


@frappe.whitelist()
def my_subscription_url():
    """Return (and lazily generate) the current user's subscribe URL."""
    import secrets
    user = frappe.session.user
    if user in ("Guest",):
        frappe.throw("Login required")

    token = frappe.db.get_value("User", user, "calendar_token")
    if not token:
        token = secrets.token_urlsafe(24)
        # Stored as a custom field added by the install routine
        frappe.db.set_value("User", user, "calendar_token", token,
                            update_modified=False)
        frappe.db.commit()

    base = (get_url() or "").rstrip("/")
    return {
        "url": f"{base}/api/method/isc_pmo.pmo_integrations.calendar_feed.feed?token={token}",
    }
