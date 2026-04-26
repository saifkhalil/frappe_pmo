"""Strategic / OKR core logic.

Implements the rollup math and check-in snapshot semantics described in the
Advisicon PDF, adapted to Frappe v15 controllers.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

import frappe
from frappe.utils import flt, getdate, nowdate

from isc_pmo.strategic.math_utils import kr_progress_pct as _kr_progress_pct
from isc_pmo.strategic.math_utils import weighted_average


# ---------------------------------------------------------------------------
# Key Result progress math
# ---------------------------------------------------------------------------


def compute_kr_progress(doc, method=None):
    """Recompute progress_pct on a Key Result based on starting/current/target
    and measure_direction. Also derives time_based_status from dates/status."""
    start = flt(doc.starting_point)
    current = flt(doc.current_value)
    target = flt(doc.target_value)
    direction = (doc.measure_direction or "Increase").strip()

    progress = _kr_progress_pct(start, current, target, direction)
    doc.progress_pct = progress

    doc.time_based_status = _time_based_status(doc)


def _time_based_status(doc) -> str:
    if (doc.status or "") in ("Closed", "Cancelled"):
        return "Complete" if doc.status == "Closed" else "Cancelled"
    if not doc.target_date:
        return "No Target Date"
    today = getdate(nowdate())
    target = getdate(doc.target_date)
    if target < today:
        return "Past Due"
    delta_days = (target - today).days
    if delta_days <= 30:
        return "Due in 1 Month"
    if delta_days <= 90:
        return "Due in 3 Months"
    return "On Time"


# ---------------------------------------------------------------------------
# Check-in snapshot + apply
# ---------------------------------------------------------------------------


def snapshot_check_in(doc, method=None):
    """Before insert: capture immutable snapshot fields from the parent KR."""
    if not doc.key_result:
        return
    kr = frappe.db.get_value(
        "Key Result",
        doc.key_result,
        ["starting_point", "target_value", "measure_direction", "weight_pct"],
        as_dict=True,
    )
    if not kr:
        return
    doc.baseline_snap = kr.starting_point
    doc.target_snap = kr.target_value
    doc.measure_direction_snap = kr.measure_direction
    doc.weight_pct_snap = kr.weight_pct

    # Compute progress at check-in time using snapshot semantics
    doc.progress_pct_at_checkin = _kr_progress_pct(
        flt(kr.starting_point),
        flt(doc.current_value),
        flt(kr.target_value),
        kr.measure_direction or "Increase",
    )


def apply_check_in_to_kr(doc, method=None):
    """After insert: if apply_to_kr is Yes, push current_value to the KR."""
    if not doc.key_result or doc.apply_to_kr != "Yes":
        return
    kr = frappe.get_doc("Key Result", doc.key_result)
    kr.current_value = doc.current_value
    if doc.confidence is not None:
        kr.confidence = doc.confidence
    kr.last_check_in_date = doc.check_in_date
    kr.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Strategic Objective rollup
# ---------------------------------------------------------------------------


def trigger_objective_rollup(doc, method=None):
    """When a Key Result changes, recompute parent Objective progress."""
    if not doc.strategic_objective:
        return
    obj = frappe.get_doc("Strategic Objective", doc.strategic_objective)
    rollup_objective(obj)
    obj.save(ignore_permissions=True)


def rollup_objective(doc, method=None):
    """Recompute progress_pct on a Strategic Objective.

    Modes:
      - Manual: user-entered, leave alone
      - Auto: weighted average of child Key Result progress_pct
    """
    if (doc.progress_mode or "Manual") != "Auto":
        return

    krs = frappe.get_all(
        "Key Result",
        filters={"strategic_objective": doc.name, "is_active": 1},
        fields=["name", "progress_pct", "weight_pct"],
    )
    if not krs:
        doc.progress_pct = 0
        return

    pairs = [(flt(k.progress_pct), flt(k.weight_pct)) for k in krs]
    doc.progress_pct = weighted_average(pairs)


# ---------------------------------------------------------------------------
# Daily scheduler — refresh time_based_status across all active KRs
# ---------------------------------------------------------------------------


def recompute_time_based_status():
    krs = frappe.get_all(
        "Key Result",
        filters={"is_active": 1},
        fields=["name", "status", "target_date"],
    )
    for k in krs:
        new_status = _time_based_status(frappe._dict(k))
        frappe.db.set_value("Key Result", k.name, "time_based_status", new_status, update_modified=False)
    frappe.db.commit()
