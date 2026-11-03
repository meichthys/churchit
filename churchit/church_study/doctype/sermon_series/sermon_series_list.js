// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Sermon Series"] = {
	hide_name_column: true,
	hide_name_filter: true,
	add_fields: ["publish"],
	get_indicator(doc) {
		if (doc.publish) return [__("Published"), "blue", "publish,=,1"];
	},
};
