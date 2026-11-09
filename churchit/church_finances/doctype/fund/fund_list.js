// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Fund"] = {
	hide_name_column: true,
	hide_name_filter: true,
	add_fields: ["balance", "allow_giving"],
	get_indicator(doc) {
		if (doc.balance < 0) return [__("Overdrawn"), "red", "balance,<,0"];
		if (doc.allow_giving)
			return [__("Open for Giving"), "green", "allow_giving,=,1"];
		return [__("Internal"), "gray", "allow_giving,=,0"];
	},
};
