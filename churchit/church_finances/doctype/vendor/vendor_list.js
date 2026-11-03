// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Vendor"] = {
	hide_name_column: true,
	hide_name_filter: true,
	add_fields: ["is_active"],
	get_indicator(doc) {
		return doc.is_active
			? [__("Active"), "green", "is_active,=,1"]
			: [__("Inactive"), "gray", "is_active,=,0"];
	},
};
