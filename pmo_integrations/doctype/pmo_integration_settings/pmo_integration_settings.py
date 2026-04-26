"""Controller for PMO Integration Settings."""
from __future__ import annotations

import frappe
from frappe.model.document import Document


class PMOIntegrationSettings(Document):
    pass


@frappe.whitelist()
def send_test():
    from isc_pmo.pmo_integrations.teams import send_test_message
    return send_test_message()
