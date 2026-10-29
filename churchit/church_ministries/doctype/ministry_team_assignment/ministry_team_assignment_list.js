// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Ministry Team Assignment"] = {
	onload(listview) {
		if (!frappe.model.can_create("Ministry Team Assignment")) return;
		listview.page.add_inner_button(__("Send Requests Now"), () => {
			frappe.call({
				method: "churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment.send_team_emails_now",
				freeze: true,
				freeze_message: __("Sending..."),
				callback: (r) => {
					frappe.show_alert({
						message: r.message
							? __("{0} messages sent.", [r.message])
							: __("There are no messages to send."),
						indicator: "green",
					});
					listview.refresh();
				},
			});
		});
	},
};
