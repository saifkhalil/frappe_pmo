"""Controller for PMO MS365 Settings."""
from __future__ import annotations

import frappe
from frappe.model.document import Document


class PMOMS365Settings(Document):
    pass


@frappe.whitelist()
def setup_microsoft_login():
    """Create / refresh the 'Office 365' Social Login Key from these settings."""
    s = frappe.get_cached_doc("PMO MS365 Settings")
    if not (s.enabled and s.enable_microsoft_login):
        frappe.throw("Enable both 'Enable Microsoft 365 Integration' and 'Enable Microsoft Sign-in (SSO)' first.")
    if not (s.tenant_id and s.client_id and s.client_secret):
        frappe.throw("Tenant ID, Client ID and Client Secret are required.")

    name = "Office 365"
    if frappe.db.exists("Social Login Key", name):
        slk = frappe.get_doc("Social Login Key", name)
    else:
        slk = frappe.new_doc("Social Login Key")
        slk.social_login_provider = "Office 365"
        slk.provider_name = name

    slk.client_id = s.client_id
    slk.client_secret = s.get_password("client_secret")
    slk.base_url = f"https://login.microsoftonline.com/{s.tenant_id}"
    slk.authorize_url = "/oauth2/v2.0/authorize"
    slk.access_token_url = "/oauth2/v2.0/token"
    slk.api_endpoint = "https://graph.microsoft.com/v1.0/me"
    slk.redirect_url = "/api/method/frappe.integrations.oauth2_logins.login_via_office_365"
    slk.icon = "fa fa-windows"
    slk.enable_social_login = 1
    slk.sign_ups = "Allow"
    slk.flags.ignore_permissions = True
    slk.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "name": slk.name}
