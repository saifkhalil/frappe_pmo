// Add "Connect Outlook" / "Disconnect Outlook" buttons on the User form.
frappe.ui.form.on("User", {
    refresh(frm) {
        // Only show on the current user's own profile (or to admins on any user).
        const is_self = frm.doc.name === frappe.session.user;
        const is_admin = frappe.user.has_role("System Manager") || frappe.user.has_role("PMO Admin");
        if (!(is_self || is_admin)) return;

        frm.add_custom_button(__("Connect Outlook"), () => {
            frappe.call({
                method: "isc_pmo.pmo_integrations.ms_graph.connect_outlook",
                callback: (r) => {
                    if (r.message && r.message.url) window.open(r.message.url, "_blank");
                },
            });
        }, __("Microsoft 365"));

        frm.add_custom_button(__("Disconnect Outlook"), () => {
            frappe.confirm(__("Disconnect Outlook calendar?"), () => {
                frappe.call({
                    method: "isc_pmo.pmo_integrations.ms_graph.disconnect_outlook",
                    callback: () => frappe.show_alert({
                        message: __("Outlook disconnected."), indicator: "orange"
                    }),
                });
            });
        }, __("Microsoft 365"));

        frm.add_custom_button(__("My Calendar (.ics) URL"), () => {
            frappe.call({
                method: "isc_pmo.pmo_integrations.calendar_feed.my_subscription_url",
                callback: (r) => {
                    if (r.message && r.message.url) {
                        frappe.msgprint({
                            title: __("Personal Calendar Subscription"),
                            message: `<p>${__("Paste this URL into Outlook / Google Calendar / Apple Calendar (Subscribe from URL):")}</p>
                                      <pre style="white-space:pre-wrap;word-break:break-all">${frappe.utils.escape_html(r.message.url)}</pre>`,
                            indicator: "blue",
                        });
                    }
                },
            });
        }, __("Microsoft 365"));
    },
});
