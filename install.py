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
