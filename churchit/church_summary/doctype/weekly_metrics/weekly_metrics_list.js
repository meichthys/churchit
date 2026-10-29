// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Weekly Metrics"] = {
	onload(listview) {
		if (!frappe.user.has_role(["Church Manager", "System Manager"])) return;
		listview.page.add_inner_button(__("Fill the Last 52 Weeks"), () => {
			frappe.call({ method: "churchit.church_summary.metrics.backfill" }).then(() => {
				frappe.show_alert({
					message: __(
						"The attendance and giving of the last 52 weeks are being filled in. Refresh the list in a few minutes."
					),
					indicator: "green",
				});
			});
		});
	},
};
