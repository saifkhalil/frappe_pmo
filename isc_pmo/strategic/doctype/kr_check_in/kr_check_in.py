from __future__ import annotations

from frappe.model.document import Document


class KRCheckIn(Document):
    """Snapshot + apply logic is wired in `hooks.py` (before_insert, after_insert)."""

    pass
