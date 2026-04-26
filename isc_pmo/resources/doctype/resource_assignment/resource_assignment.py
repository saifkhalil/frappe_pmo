from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ResourceAssignment(Document):
    def validate(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            frappe.throw("Start Date must be before End Date")
        self._compute_completion()

    def _compute_completion(self):
        """Sum hours from ERPNext Timesheet Detail for the linked employee/project."""
        if not (self.bookable_resource and self.project):
            self.completed_hours = 0
            self.remaining_hours = flt(self.allocated_hours)
            return

        employee = frappe.db.get_value("Bookable Resource", self.bookable_resource, "employee")
        if not employee:
            self.completed_hours = 0
        else:
            rows = frappe.db.sql(
                """
                SELECT COALESCE(SUM(td.hours), 0) AS hrs
                FROM `tabTimesheet Detail` td
                INNER JOIN `tabTimesheet` ts ON ts.name = td.parent
                WHERE ts.employee = %(emp)s
                  AND td.project = %(proj)s
                  AND td.from_time >= %(start)s
                  AND td.to_time <= %(end)s
                  AND ts.docstatus < 2
                """,
                {"emp": employee, "proj": self.project, "start": self.start_date, "end": self.end_date},
                as_dict=True,
            )
            self.completed_hours = flt(rows[0].hrs) if rows else 0

        self.remaining_hours = max(0, flt(self.allocated_hours) - flt(self.completed_hours))
