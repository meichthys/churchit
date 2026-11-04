// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Function Check-In"] = {
	hide_name_column: true,
	hide_name_filter: true,
	add_fields: ["security_code", "collected_at"],
	// A pickup code means a child who leaves only through Verify Pickup.
	get_indicator(doc) {
		if (doc.security_code && doc.collected_at)
			return [__("Picked Up"), "green", "security_code,is,set|collected_at,is,set"];
		if (doc.security_code)
			return [
				__("Awaiting Pickup"),
				"orange",
				"security_code,is,set|collected_at,is,not set",
			];
		if (doc.collected_at)
			return [__("Checked Out"), "gray", "security_code,is,not set|collected_at,is,set"];
	},
	onload(listview) {
		listview.page.add_inner_button(__("Check-In Station"), () => frappe.set_route("check-in"));
		listview.page.add_action_item(__("Print Name Tags"), () => {
			const check_ins = listview.get_checked_items().map((row) => row.name);
			if (!check_ins.length) return frappe.msgprint(__("Select at least one check-in."));
			church.name_tags.print_for({ check_ins });
		});
	},
};
