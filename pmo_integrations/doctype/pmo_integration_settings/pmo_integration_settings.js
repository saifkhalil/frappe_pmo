// Add a "Send Test Message" button to the settings form.
frappe.ui.form.on("PMO Integration Settings", {
    refresh(frm) {
        frm.add_custom_button(__("Send Test to Teams"), () => {
            frappe.call({
                method: "isc_pmo.pmo_integrations.doctype.pmo_integration_settings.pmo_integration_settings.send_test",
                freeze: true,
                freeze_message: __("Posting test card…"),
                callback: () => frappe.show_alert({message: __("Sent — check the Teams channel."), indicator: "green"}),
            });
        }, __("Actions"));

        frm.add_custom_button(__("My Calendar URL"), () => {
            frappe.call({
                method: "isc_pmo.pmo_integrations.calendar_feed.my_subscription_url",
                callback: (r) => {
                    if (r.message && r.message.url) {
                        frappe.msgprint({
                            title: __("Personal Calendar Subscription"),
                            message: `<p>${__("Paste this URL into Outlook / Google Calendar / Apple Calendar:")}</p>
                                      <pre style="white-space:pre-wrap;word-break:break-all">${frappe.utils.escape_html(r.message.url)}</pre>`,
                            indicator: "blue",
                        });
                    }
                },
            });
        }, __("Actions"));
    },
});
