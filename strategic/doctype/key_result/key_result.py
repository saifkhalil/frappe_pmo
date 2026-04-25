from __future__ import annotations

from frappe.model.document import Document


class KeyResult(Document):
    """Lifecycle hooks are wired in `hooks.py` and execute the helpers in
    `isc_pmo.strategic.utils` (compute_kr_progress, trigger_objective_rollup)."""

    pass
