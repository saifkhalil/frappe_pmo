from __future__ import annotations

import frappe
from frappe.model.document import Document

from isc_pmo.strategic.utils import rollup_objective


class StrategicObjective(Document):
    def validate(self):
        if self.start_date and self.target_date and self.start_date > self.target_date:
            frappe.throw("Start Date must be before Target Date")
        rollup_objective(self)
