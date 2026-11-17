// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// The report view runs these settings too, so a saved smart list offers the same actions.
frappe.listview_settings["Person"] = {
	hide_name_column: true,
	hide_name_filter: true,
	add_fields: ["membership_status"],
	filters: [["membership_status", "=", "Active"]],
	get_indicator(doc) {
		const colors = { Active: "green", Inactive: "gray" };
		const status = doc.membership_status;
		if (!status) return;
		return [__(status), colors[status] || "blue", `membership_status,=,${status}`];
	},
	onload(listview) {
		// Every church's people show here, so desk.css keeps the Church filter even for one church.
		if (frappe.boot.churchit.shared_people)
			listview.page.wrapper.addClass("churchit-shared-people");
		listview.page.add_inner_button(__("Rolodex"), () => {
			frappe.route_options = { view: "people" };
			frappe.set_route("rolodex");
		});
		churchit.ai.add_describe_people(listview);
		// Frappe adds its own Edit, Assign To and Add Tags.
		const actions = churchit.people_actions.get([
			"new_church_email",
			"email",
			"email_household_adults",
			"open_in_rolodex",
			"add_to_group",
			"verify_contact_info",
			"mark_inactive",
			"check_in",
			"print_name_tags",
		]);
		for (const action of actions) {
			listview.page.add_action_item(action.label, () => {
				const people = listview.get_checked_items(true);
				if (!people.length) return frappe.msgprint(__("Select at least one person."));
				action.run(people, () => listview.refresh());
			});
		}
	},
};
