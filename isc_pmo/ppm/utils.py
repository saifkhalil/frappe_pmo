"""PPM (Portfolio / Program / Project) rollups and registration → project bridge."""
from __future__ import annotations

import frappe
from frappe.utils import flt


HEALTH_RANK = {"Green": 0, "Yellow": 1, "Red": 2}
RANK_HEALTH = {v: k for k, v in HEALTH_RANK.items()}


# ---------------------------------------------------------------------------
# Program rollup
# ---------------------------------------------------------------------------


def trigger_program_rollup(doc, method=None):
    """Triggered on Project on_update; recompute parent Program counters."""
    program = (doc.get("custom_program") if hasattr(doc, "get") else None) or getattr(doc, "custom_program", None)
    if not program:
        return
    recompute_program_rollup(program)


def recompute_program_rollup(program: str):
    if not frappe.db.exists("Program", program):
        return
    rows = frappe.get_all(
        "Project",
        filters={"custom_program": program, "status": ["!=", "Cancelled"]},
        fields=[
            "name", "status",
            "custom_overall_health", "custom_schedule_health",
            "custom_financial_health", "custom_issue_health",
        ],
    )
    active = sum(1 for r in rows if r.status in ("Open", "Completed"))
    on_track = sum(1 for r in rows if r.custom_overall_health == "Green")
    at_risk = sum(1 for r in rows if r.custom_overall_health == "Yellow")
    in_trouble = sum(1 for r in rows if r.custom_overall_health == "Red")

    pg = frappe.get_doc("Program", program)
    pg.active_projects = active
    pg.projects_on_track = on_track
    pg.projects_at_risk = at_risk
    pg.projects_in_trouble = in_trouble
    pg.overall_health = _aggregate_health([r.custom_overall_health for r in rows])
    pg.schedule_health = _aggregate_health([r.custom_schedule_health for r in rows])
    pg.financial_health = _aggregate_health([r.custom_financial_health for r in rows])
    pg.issue_health = _aggregate_health([r.custom_issue_health for r in rows])
    pg.save(ignore_permissions=True)

    if pg.portfolio:
        recompute_portfolio_rollup(pg.portfolio)


def _aggregate_health(values):
    """Worst-of aggregation: Red beats Yellow beats Green."""
    ranks = [HEALTH_RANK[v] for v in values if v in HEALTH_RANK]
    if not ranks:
        return None
    return RANK_HEALTH[max(ranks)]


# ---------------------------------------------------------------------------
# Portfolio rollup
# ---------------------------------------------------------------------------


def recompute_portfolio_rollup(portfolio: str):
    if not frappe.db.exists("Portfolio", portfolio):
        return
    programs = frappe.get_all(
        "Program",
        filters={"portfolio": portfolio},
        fields=[
            "name", "active_projects", "projects_on_track",
            "projects_at_risk", "projects_in_trouble",
            "overall_health", "schedule_health", "financial_health", "issue_health",
        ],
    )
    pf = frappe.get_doc("Portfolio", portfolio)
    pf.active_projects = sum(int(p.active_projects or 0) for p in programs)
    pf.projects_on_track = sum(int(p.projects_on_track or 0) for p in programs)
    pf.projects_at_risk = sum(int(p.projects_at_risk or 0) for p in programs)
    pf.projects_in_trouble = sum(int(p.projects_in_trouble or 0) for p in programs)
    pf.overall_health = _aggregate_health([p.overall_health for p in programs])
    pf.schedule_health = _aggregate_health([p.schedule_health for p in programs])
    pf.financial_health = _aggregate_health([p.financial_health for p in programs])
    pf.issue_health = _aggregate_health([p.issue_health for p in programs])
    pf.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------


def recompute_all_program_rollups():
    for name in frappe.get_all("Program", pluck="name"):
        try:
            recompute_program_rollup(name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Program rollup failed: {name}")
    frappe.db.commit()


def recompute_all_portfolio_rollups():
    for name in frappe.get_all("Portfolio", pluck="name"):
        try:
            recompute_portfolio_rollup(name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Portfolio rollup failed: {name}")
    frappe.db.commit()


# ---------------------------------------------------------------------------
# Project Registration → Project conversion
# ---------------------------------------------------------------------------


def on_registration_workflow_change(doc, method=None):
    """When a Project Registration reaches workflow_state == 'Approved',
    auto-create an ERPNext Project linked back to the registration."""
    if doc.workflow_state != "Approved":
        return
    if doc.created_project:
        return  # idempotent

    project = frappe.get_doc({
        "doctype": "Project",
        "project_name": doc.project_name,
        "expected_start_date": doc.estimated_start_date,
        "expected_end_date": doc.estimated_end_date,
        "estimated_costing": flt(doc.project_total_budget),
        "company": doc.company or frappe.defaults.get_user_default("Company"),
        "custom_project_registration": doc.name,
        "custom_portfolio": doc.portfolio,
        "custom_program": doc.program,
        "custom_strategic_objective": doc.strategic_objective,
        "custom_executive_sponsor": doc.executive_sponsor,
        "custom_business_unit": doc.business_unit,
        "custom_pmo_priority": doc.priority,
    }).insert(ignore_permissions=True)

    doc.db_set("created_project", project.name, update_modified=False)
    frappe.msgprint(f"Project {project.name} created from registration {doc.name}")
