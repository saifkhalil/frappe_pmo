from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import flt


PRIORITY_WEIGHT = {
    "(1) Critical": 5,
    "(2) High": 4,
    "(3) Moderate": 3,
    "(4) Low": 2,
    "(5) Optional": 1,
}


class ProjectRegistration(Document):
    def validate(self):
        self._compute_roi()
        self._compute_prioritization_score()

    def _compute_roi(self):
        budget = flt(self.project_total_budget)
        benefits = flt(self.cost_benefits)
        self.roi = round((benefits - budget) / budget, 4) if budget else 0

    def _compute_prioritization_score(self):
        # Weighted blend of ROI (capped at 5), strategic flag, priority weight
        roi_score = max(min(flt(self.roi), 5.0), -1.0)
        strategic = 2.0 if self.is_strategic else 0.0
        priority = PRIORITY_WEIGHT.get(self.priority, 0)
        # Scale to 0..100
        raw = (roi_score + strategic + priority) / 12.0 * 100.0
        self.prioritization_score = round(max(0.0, min(100.0, raw)), 2)
