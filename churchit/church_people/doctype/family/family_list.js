// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Family"] = {
	hide_name_column: true,
	hide_name_filter: true,
	onload(listview) {
		listview.page.add_inner_button(__("Rolodex"), () => {
			frappe.route_options = { view: "households" };
			frappe.set_route("rolodex");
		});
		listview.page.add_action_item(__("Email"), () => {
			const families = listview.get_checked_items(true);
			if (!families.length)
				return frappe.msgprint(__("Select at least one family."));
			// Each household's own email, else its primary contact's.
			churchit.people_actions.email_in_bcc("get_household_emails", {
				families,
			});
		});
	},
};
