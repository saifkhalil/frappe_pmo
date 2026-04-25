app_name = "isc_pmo"
app_title = "ISC PMO Autopilot"
app_publisher = "International Smart Card (ISC)"
app_description = "Strategic OKR, Portfolio/Program/Project, Resource & Reporting on ERPNext"
app_email = "pmo@isc.example"
app_license = "MIT"
app_version = "0.1.0"

required_apps = ["frappe/erpnext"]

# DocType document events: rollups, snapshots, workflow side-effects
doc_events = {
    "KR Check-in": {
        "before_insert": "isc_pmo.strategic.utils.snapshot_check_in",
        "after_insert": "isc_pmo.strategic.utils.apply_check_in_to_kr",
    },
    "Key Result": {
        "validate": "isc_pmo.strategic.utils.compute_kr_progress",
        "on_update": "isc_pmo.strategic.utils.trigger_objective_rollup",
    },
    "Strategic Objective": {
        "validate": "isc_pmo.strategic.utils.rollup_objective",
    },
    "Project": {
        "on_update": "isc_pmo.ppm.utils.trigger_program_rollup",
    },
    "Project Registration": {
        "on_update_after_submit": "isc_pmo.ppm.utils.on_registration_workflow_change",
    },
}

# Scheduled rollups
scheduler_events = {
    "hourly": [
        "isc_pmo.ppm.utils.recompute_all_program_rollups",
    ],
    "daily": [
        "isc_pmo.strategic.utils.recompute_time_based_status",
        "isc_pmo.ppm.utils.recompute_all_portfolio_rollups",
    ],
}

# Fixtures shipped with the app (loaded on install / migrate).
# Each entry is exported on `bench export-fixtures` and re-imported on install.
fixtures = [
    {"dt": "Role", "filters": [["name", "in", [
        "PMO Admin", "Portfolio Manager", "Program Manager",
        "Project Manager", "Sponsor", "OKR Owner", "Resource Manager"
    ]]]},
    {"dt": "Custom Field", "filters": [["dt", "=", "Project"], ["name", "like", "Project-%"]]},
    {"dt": "Workflow", "filters": [["name", "=", "Project Registration Approval"]]},
    {"dt": "Workflow State", "filters": [["name", "in", [
        "Draft", "In Review", "Sponsor Approval", "PMO Approval", "Approved", "Rejected"
    ]]]},
    {"dt": "Workflow Action Master", "filters": [["name", "in", [
        "Submit for Review", "Sponsor Approve", "PMO Approve", "Reject"
    ]]]},
    {"dt": "Number Card", "filters": [["name", "like", "PMO -%"]]},
    {"dt": "Dashboard Chart", "filters": [["name", "like", "PMO -%"]]},
    {"dt": "Dashboard", "filters": [["name", "=", "ISC PMO Autopilot Overview"]]},
]

# After-install hook seeds roles, naming series, demo data flag
after_install = "isc_pmo.install.after_install"

# Standard whitelisted methods (via /api/method/...)
# Power BI endpoints live under isc_pmo.api.powerbi.*

# Includes (none for now)
app_include_css = []
app_include_js = []
