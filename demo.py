"""Demo data installer.

Run inside a Frappe v15 container/bench:

    bench --site pmo.localhost execute isc_pmo.demo.install_demo_data

Mirrors the sample names from the Advisicon Project Accelerator PDF so screens
match the reference deck for stakeholder demos.
"""
from __future__ import annotations

from datetime import date

import frappe


def install_demo_data():
    _ensure_period()
    imps = _seed_imperatives()
    objs = _seed_objectives(imps)
    krs = _seed_key_results(objs)
    _seed_check_ins(krs)
    _seed_portfolios_programs()
    _seed_bookable_resources()
    frappe.db.commit()
    print("ISC PMO Autopilot — demo data installed.")


def _ensure_period():
    if frappe.db.exists("Strategic Period", "FY24-26"):
        return
    frappe.get_doc({
        "doctype": "Strategic Period",
        "period_code": "FY24-26",
        "period_name": "Fiscal Year 2024-2026",
        "start_date": "2024-10-01",
        "target_date": "2026-12-31",
        "is_active": 1,
    }).insert(ignore_permissions=True)


def _seed_imperatives() -> dict[str, str]:
    out: dict[str, str] = {}
    for nm in [
        "Digital and Data Excellence",
        "Healthy Ecosystem Solutions",
        "Customer Experience Excellence",
        "Innovation & Growth",
        "Operational Efficiency",
    ]:
        existing = frappe.db.exists("Imperative", {"imperative_name": nm})
        if existing:
            out[nm] = existing
            continue
        d = frappe.get_doc({
            "doctype": "Imperative",
            "imperative_name": nm,
            "is_active": 1,
            "strategic_period": "FY24-26",
            "start_date": "2025-01-01",
            "target_date": "2027-12-31",
            "description": f"Strategic imperative: {nm}",
        }).insert(ignore_permissions=True)
        out[nm] = d.name
    return out


def _seed_objectives(imperatives: dict[str, str]) -> dict[str, str]:
    rows = [
        ("Increase team productivity", "Digital and Data Excellence", "Auto", 75, "On Track"),
        ("Impact and value for the money", "Operational Efficiency", "Auto", 90, "On Track"),
        ("Commitment to our mission", "Customer Experience Excellence", "Manual", 50, "At Risk"),
        ("Reduce Ticket Backlog by 50%", "Healthy Ecosystem Solutions", "Auto", 80, "On Track"),
        ("Digital and Data", "Digital and Data Excellence", "Auto", 70, "Off Track"),
    ]
    out: dict[str, str] = {}
    for title, imp_name, mode, conf, status in rows:
        existing = frappe.db.exists("Strategic Objective", {"title": title})
        if existing:
            out[title] = existing
            continue
        d = frappe.get_doc({
            "doctype": "Strategic Objective",
            "title": title,
            "is_active": 1,
            "strategic_period": "FY24-26",
            "progress_mode": mode,
            "confidence": conf,
            "status": status,
            "start_date": "2025-10-01",
            "target_date": "2026-07-01",
            "description": title,
        }).insert(ignore_permissions=True)
        out[title] = d.name
        # link to Imperative
        if imp_name in imperatives:
            imp = frappe.get_doc("Imperative", imperatives[imp_name])
            imp.append("objectives", {"strategic_objective": d.name, "alignment_strength": "Primary"})
            imp.save(ignore_permissions=True)
    return out


def _seed_key_results(objectives: dict[str, str]) -> dict[str, str]:
    rows = [
        # (kr_name, objective_title, start, current, target, weight, direction, status)
        ("Improve Teams Perception of Performance", "Increase team productivity", 4, 5.5, 8, 50, "Increase", "Off Track"),
        ("Costs Increased Instead", "Increase team productivity", 0, 0, 215, 50, "Decrease", "Not Started"),
        ("Achieve $50M in new Annual Recurring Revenue", "Impact and value for the money", 0, 50_000_000, 50_000_000, 50, "Increase", "Closed"),
        ("Customer Satisfaction Score", "Impact and value for the money", 0, 100_000_000, 100_000_000, 50, "Increase", "Closed"),
        ("Increase NPS from 45 to 60", "Commitment to our mission", 45, 45, 60, 100, "Increase", "Not Started"),
        ("Reduce demo bugs 7 to 3", "Digital and Data", 7, 5, 3, 60, "Decrease", "Off Track"),
        ("Delayed Low Progress", "Reduce Ticket Backlog by 50%", 0, 25, 160, 100, "Increase", "Off Track"),
    ]
    out: dict[str, str] = {}
    for kr_name, obj_title, start, cur, tgt, wt, direction, status in rows:
        if frappe.db.exists("Key Result", {"kr_name": kr_name}):
            out[kr_name] = frappe.db.get_value("Key Result", {"kr_name": kr_name}, "name")
            continue
        if obj_title not in objectives:
            continue
        d = frappe.get_doc({
            "doctype": "Key Result",
            "kr_name": kr_name,
            "is_active": 1,
            "strategic_objective": objectives[obj_title],
            "strategic_period": "FY24-26",
            "starting_point": start,
            "current_value": cur,
            "target_value": tgt,
            "weight_pct": wt,
            "measure_direction": direction,
            "status": status,
            "kr_type": "Metric",
            "unit": "#",
            "start_date": "2025-10-01",
            "target_date": "2026-01-02",
        }).insert(ignore_permissions=True)
        out[kr_name] = d.name
    return out


def _seed_check_ins(krs: dict[str, str]):
    target_kr = krs.get("Improve Teams Perception of Performance")
    if not target_kr:
        return
    if frappe.db.exists("KR Check-in", {"checkin_name": "_TR 4th Quarter 2nd Update"}):
        return
    frappe.get_doc({
        "doctype": "KR Check-in",
        "checkin_name": "_TR 4th Quarter 2nd Update",
        "key_result": target_kr,
        "check_in_date": "2025-12-15 07:39:00",
        "current_value": 5.5,
        "confidence": 60,
        "apply_to_kr": "No",
        "message": "Q4 update — slipped on training cadence.",
    }).insert(ignore_permissions=True)


def _seed_portfolios_programs():
    portfolios = [
        ("AI & Automation", "Yellow"),
        ("Cloud Migration", "Green"),
        ("Customer Experience", "Green"),
        ("Cybersecurity", "Yellow"),
        ("Data & Analytics", "Green"),
        ("Digital Transformation 2026", "Red"),
        ("Finance Modernization", "Red"),
    ]
    for nm, health in portfolios:
        if frappe.db.exists("Portfolio", nm):
            continue
        frappe.get_doc({
            "doctype": "Portfolio",
            "portfolio_name": nm,
            "is_global": 1,
            "overall_health": health,
            "schedule_health": health,
            "financial_health": health,
            "issue_health": health,
            "start_date": "2026-02-02",
            "end_date": "2026-10-10",
            "description": f"Portfolio: {nm}",
        }).insert(ignore_permissions=True)

    programs = [
        ("Data Warehouse Program", "Cloud Migration", "Green", 12_000_000, 13_000_000),
        ("ERP Cloud Migration", "Cloud Migration", "Red", 8_500_000, 9_000_000),
        ("Finance Reporting Revamp", "Finance Modernization", "Green", 4_200_000, 5_000_000),
        ("Global Sales Modernization", "AI & Automation", "Red", 11_000_000, 14_000_000),
    ]
    for nm, pf, health, budget, benefit in programs:
        if frappe.db.exists("Program", nm):
            continue
        frappe.get_doc({
            "doctype": "Program",
            "program_name": nm,
            "portfolio": pf,
            "state": "(1) In Progress",
            "priority": "(3) Moderate",
            "overall_health": health,
            "schedule_health": health,
            "financial_health": health,
            "issue_health": health,
            "budget": budget,
            "financial_benefit": benefit,
            "program_start": "2026-03-04",
            "program_due": "2026-12-09",
        }).insert(ignore_permissions=True)


def _seed_bookable_resources():
    rows = [
        ("_Developer", "Generic"),
        ("_GenericR", "Generic"),
        ("_EquipmentR", "Equipment"),
        ("_CrewR", "Crew"),
        ("_PoolR", "Pool"),
    ]
    for nm, rtype in rows:
        if frappe.db.exists("Bookable Resource", nm):
            continue
        frappe.get_doc({
            "doctype": "Bookable Resource",
            "resource_name": nm,
            "resource_type": rtype,
            "is_active": 1,
            "capacity_hours_per_week": 40,
        }).insert(ignore_permissions=True)
