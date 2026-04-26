frappe.ui.form.on("PMO MS365 Settings", {
    refresh(frm) {
        if (!frm.doc.redirect_uri) {
            frm.set_value("redirect_uri",
                window.location.origin + "/api/method/isc_pmo.pmo_integrations.ms_graph.oauth_callback");
        }
        frm.add_custom_button(__("Setup Microsoft Login"), () => {
            frappe.call({
                method: "isc_pmo.pmo_integrations.doctype.pmo_ms365_settings.pmo_ms365_settings.setup_microsoft_login",
                freeze: true,
                callback: () => frappe.show_alert({
                    message: __("Social Login Key 'Office 365' configured. Sign-out and the Login page will show 'Sign in with Office 365'."),
                    indicator: "green",
                }),
            });
        }, __("Actions"));
    },
});
