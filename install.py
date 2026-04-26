"""Install hook — seeds roles, naming series, default Strategic Period."""
from __future__ import annotations

import frappe


ROLES = [
    "PMO Admin",
    "Portfolio Manager",
    "Program Manager",
    "Project Manager",
    "Sponsor",
    "OKR Owner",
    "Resource Manager",
]


def after_install():
    _create_roles()
    _seed_naming_series()
    _seed_default_strategic_period()
    _add_user_calendar_token_field()
    _add_task_outlook_event_field()
    create_workspaces()
    frappe.db.commit()


def _create_roles():
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": 1,
            }).insert(ignore_permissions=True)


def _seed_naming_series():
    # naming series are declared per DocType; nothing to seed globally yet
    return


def _seed_default_strategic_period():
    if frappe.db.exists("Strategic Period", {"period_code": "FY26-27"}):
        return
    frappe.get_doc({
        "doctype": "Strategic Period",
        "period_code": "FY26-27",
        "period_name": "Fiscal Year 2026-2027",
        "start_date": "2026-01-01",
        "target_date": "2027-12-31",
        "is_active": 1,
    }).insert(ignore_permissions=True)


def _add_user_calendar_token_field():
    """Add a hidden 'calendar_token' field to User for personal ICS feeds."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    create_custom_field("User", {
        "fieldname": "calendar_token",
        "label": "Calendar Token",
        "fieldtype": "Data",
        "hidden": 1,
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "username",
    }, is_system_generated=True)


def _add_task_outlook_event_field():
    """Add a hidden 'outlook_event_id' on Task to track the synced calendar event."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    create_custom_field("Task", {
        "fieldname": "outlook_event_id",
        "label": "Outlook Event ID",
        "fieldtype": "Data",
        "hidden": 1,
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "subject",
    }, is_system_generated=True)


# ---------------------------------------------------------------------------
# Workspaces (sidebar entries)
# ---------------------------------------------------------------------------

WORKSPACES = [
    {
        "name": "Project Management",
        "title": "Project Management",
        "icon": "project",
        "module": "PMO Reports",
        "sequence_id": 20.0,
        "shortcuts": [
            {"label": "Dashboard", "type": "Dashboard", "link_to": "ISC PMO Autopilot Overview"},
            {"label": "Imperatives", "type": "DocType", "link_to": "Imperative"},
            {"label": "Strategic Objectives", "type": "DocType", "link_to": "Strategic Objective"},
            {"label": "Key Results", "type": "DocType", "link_to": "Key Result"},
            {"label": "KR Check-ins", "type": "DocType", "link_to": "KR Check In"},
            {"label": "Portfolios", "type": "DocType", "link_to": "Portfolio"},
            {"label": "Programs", "type": "DocType", "link_to": "Program"},
            {"label": "Projects", "type": "DocType", "link_to": "Project"},
            {"label": "Project Registrations", "type": "DocType", "link_to": "Project Registration"},
            {"label": "Bookable Resources", "type": "DocType", "link_to": "Bookable Resource"},
        ],
        "links": [
            ("Card Break", "Strategic", None),
            ("Link", "Imperative", "Imperative"),
            ("Link", "Strategic Objective", "Strategic Objective"),
            ("Link", "Key Result", "Key Result"),
            ("Link", "KR Check In", "KR Check In"),
            ("Link", "Strategic Period", "Strategic Period"),
            ("Card Break", "Portfolios & Programs", None),
            ("Link", "Portfolio", "Portfolio"),
            ("Link", "Program", "Program"),
            ("Link", "Project", "Project"),
            ("Link", "Project Registration", "Project Registration"),
            ("Card Break", "Delivery", None),
            ("Link", "Status Report", "Status Report"),
            ("Link", "RAID Item", "RAID Item"),
            ("Link", "Lessons Learned", "Lessons Learned"),
            ("Card Break", "Resources", None),
            ("Link", "Bookable Resource", "Bookable Resource"),
            ("Link", "Resource Assignment", "Resource Assignment"),
        ],
    },
]


def _build_content(spec):
    """Build the workspace `content` JSON (widget layout for the body)."""
    import json as _json
    blocks = []

    blocks.append({
        "id": "header_main",
        "type": "header",
        "data": {"text": f"<span class=\"h4\"><b>{spec['title']}</b></span>", "col": 12},
    })

    shortcut_labels = [s["label"] for s in spec.get("shortcuts", [])]
    if shortcut_labels:
        blocks.append({
            "id": "header_shortcuts",
            "type": "header",
            "data": {"text": "<span class=\"h6\"><b>Your Shortcuts</b></span>", "col": 12},
        })
        for lbl in shortcut_labels:
            blocks.append({
                "id": f"sc_{lbl}",
                "type": "shortcut",
                "data": {"shortcut_name": lbl, "col": 3},
            })
        blocks.append({"id": "spacer1", "type": "spacer", "data": {"col": 12}})

    card_labels = [lbl for kind, lbl, _ in spec.get("links", []) if kind == "Card Break"]
    if card_labels:
        blocks.append({
            "id": "header_reports",
            "type": "header",
            "data": {"text": "<span class=\"h6\"><b>Reports & Masters</b></span>", "col": 12},
        })
        for lbl in card_labels:
            blocks.append({
                "id": f"card_{lbl}",
                "type": "card",
                "data": {"card_name": lbl, "col": 4},
            })

    return _json.dumps(blocks)


def create_workspaces():
    """Create / refresh ISC PMO Autopilot workspace shown in the desk sidebar."""
    for spec in WORKSPACES:
        ws_name = spec["name"]
        if frappe.db.exists("Workspace", ws_name):
            ws = frappe.get_doc("Workspace", ws_name)
            ws.shortcuts = []
            ws.links = []
        else:
            ws = frappe.new_doc("Workspace")
            ws.name = ws_name

        ws.title = spec["title"]
        ws.label = spec["title"]
        ws.icon = spec.get("icon", "folder")
        ws.module = spec.get("module")
        ws.public = 1
        ws.is_hidden = 0
        ws.sequence_id = spec.get("sequence_id", 20.0)
        ws.for_user = ""
        ws.app = "isc_pmo"

        for sc in spec.get("shortcuts", []):
            ws.append("shortcuts", {
                "label": sc["label"],
                "type": sc["type"],
                "link_to": sc["link_to"],
                "color": sc.get("color", "Blue"),
            })
        for kind, label, link_to in spec.get("links", []):
            row = {
                "label": label,
                "type": kind,
                "hidden": 0,
                "is_query_report": 0,
                "onboard": 0,
            }
            if kind == "Card Break":
                row["link_count"] = 0
            else:
                row["link_type"] = "DocType"
                row["link_to"] = link_to
            ws.append("links", row)

        ws.content = _build_content(spec)

        ws.flags.ignore_mandatory = True
        ws.flags.ignore_permissions = True
        ws.save(ignore_permissions=True)
