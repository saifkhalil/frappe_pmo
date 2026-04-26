"""Power BI / external BI integration endpoints.

All methods are decorated with `@frappe.whitelist()` and return JSON-friendly
dicts/lists. Authenticate via API key + secret in the header:
    Authorization: token <api_key>:<api_secret>

Usage in Power BI Desktop -> Get Data -> Web (Advanced):
    URL:    https://<host>/api/method/isc_pmo.api.powerbi.<endpoint>
    Header: Authorization: token <api_key>:<api_secret>
"""
from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt


# ---------------------------------------------------------------------------
# Strategic / OKR
# ---------------------------------------------------------------------------


@frappe.whitelist()
def okr_export() -> dict[str, Any]:
    """Flat OKR snapshot: Imperatives → Objectives → Key Results."""
    imperatives = frappe.get_all(
        "Imperative",
        filters={"is_active": 1},
        fields=["name", "imperative_name", "strategic_period", "owner_user", "start_date", "target_date"],
    )
    objectives = frappe.get_all(
        "Strategic Objective",
        filters={"is_active": 1},
        fields=[
            "name", "title", "strategic_period", "progress_pct", "confidence",
            "status", "owner_user", "team", "start_date", "target_date",
        ],
    )
    key_results = frappe.get_all(
        "Key Result",
        filters={"is_active": 1},
        fields=[
            "name", "kr_name", "strategic_objective", "strategic_period",
            "starting_point", "current_value", "target_value", "measure_direction",
            "weight_pct", "progress_pct", "status", "time_based_status",
            "confidence", "owner_user", "team", "kr_type", "unit",
            "start_date", "target_date", "last_check_in_date",
        ],
    )
    return {
        "imperatives": imperatives,
        "objectives": objectives,
        "key_results": key_results,
    }


@frappe.whitelist()
def kr_check_ins(days: int = 90) -> list[dict]:
    return frappe.db.sql(
        """
        SELECT name, key_result, check_in_date, current_value,
               progress_pct_at_checkin, confidence, owner_user
        FROM `tabKR Check In`
        WHERE check_in_date >= DATE_SUB(CURDATE(), INTERVAL %(d)s DAY)
        ORDER BY check_in_date DESC
        """,
        {"d": int(days)},
        as_dict=True,
    )


@frappe.whitelist()
def strategic_portfolio_overview() -> dict[str, Any]:
    """Top-of-page KPIs: Strategic Pillars (count of imperatives), Active Goals, Goal Progress %."""
    pillars = frappe.db.count("Imperative", {"is_active": 1})
    objectives = frappe.get_all(
        "Strategic Objective",
        filters={"is_active": 1},
        fields=["name", "progress_pct", "status"],
    )
    active = len(objectives)
    avg_progress = round(
        sum(flt(o.progress_pct) for o in objectives) / active, 2
    ) if active else 0
    by_status: dict[str, int] = {}
    for o in objectives:
        by_status[o.status or "Not Started"] = by_status.get(o.status or "Not Started", 0) + 1
    return {
        "strategic_pillars": pillars,
        "active_goals": active,
        "goal_progress_pct": avg_progress,
        "by_status": by_status,
    }


# ---------------------------------------------------------------------------
# PPM
# ---------------------------------------------------------------------------


@frappe.whitelist()
def portfolio_overview() -> list[dict]:
    return frappe.get_all(
        "Portfolio",
        fields=[
            "name", "portfolio_name", "portfolio_manager",
            "overall_health", "schedule_health", "financial_health", "issue_health",
            "active_projects", "projects_on_track", "projects_at_risk", "projects_in_trouble",
        ],
    )


@frappe.whitelist()
def program_overview() -> list[dict]:
    return frappe.get_all(
        "Program",
        fields=[
            "name", "program_name", "portfolio", "program_manager", "state",
            "budget", "financial_benefit", "roi",
            "overall_health", "schedule_health", "financial_health", "issue_health",
            "active_projects", "projects_on_track", "projects_at_risk", "projects_in_trouble",
        ],
    )


@frappe.whitelist()
def projects_with_pmo_fields() -> list[dict]:
    return frappe.db.sql(
        """
        SELECT p.name, p.project_name, p.status, p.percent_complete,
               p.expected_start_date, p.expected_end_date, p.estimated_costing,
               p.custom_portfolio AS portfolio, p.custom_program AS program,
               p.custom_strategic_objective AS strategic_objective,
               p.custom_pmo_project_type AS project_type,
               p.custom_overall_health AS overall_health,
               p.custom_schedule_health AS schedule_health,
               p.custom_financial_health AS financial_health,
               p.custom_issue_health AS issue_health,
               p.custom_executive_sponsor AS executive_sponsor
        FROM `tabProject` p
        WHERE p.status != 'Cancelled'
        """,
        as_dict=True,
    )


@frappe.whitelist()
def project_registrations_dashboard() -> list[dict]:
    return frappe.get_all(
        "Project Registration",
        fields=[
            "name", "project_name", "workflow_state", "customer", "project_type",
            "estimated_start_date", "estimated_end_date",
            "project_total_budget", "cost_benefits", "pm_budget",
            "roi", "prioritization_score",
            "executive_sponsor", "project_manager",
        ],
    )


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@frappe.whitelist()
def resource_dashboard() -> dict[str, Any]:
    resources = frappe.get_all(
        "Bookable Resource",
        filters={"is_active": 1},
        fields=["name", "resource_name", "resource_type", "capacity_hours_per_week"],
    )
    assignments = frappe.get_all(
        "Resource Assignment",
        fields=[
            "name", "bookable_resource", "project", "task",
            "start_date", "end_date", "allocated_hours",
            "completed_hours", "remaining_hours",
        ],
    )
    return {"resources": resources, "assignments": assignments}
