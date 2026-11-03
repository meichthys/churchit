// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Pickup Restriction"] = {
	hide_name_column: true,
	hide_name_filter: true,
	add_fields: ["valid_until"],
	get_indicator(doc) {
		if (doc.valid_until && doc.valid_until < frappe.datetime.get_today()) {
			return [__("Ended"), "gray", "valid_until,is,set|valid_until,<,Today"];
		}
		return [__("Active"), "red", "valid_until,is,not set"];
	},
};
