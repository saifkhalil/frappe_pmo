from __future__ import annotations

from frappe.model.document import Document
from frappe.utils import flt


class Program(Document):
    def validate(self):
        # ROI = (financial_benefit - budget) / budget
        budget = flt(self.budget)
        benefit = flt(self.financial_benefit)
        self.roi = round((benefit - budget) / budget, 4) if budget else 0
        # Remaining = budget - sum(child Project budgets) — placeholder until we sum from Project
        self.remaining_budget_allocation = budget
