// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Function"] = {
	hide_name_column: true,
	hide_name_filter: true,
	add_fields: ["did_not_meet", "auto_repeat", "publish"],
	get_indicator(doc) {
		if (doc.did_not_meet)
			return [__("Did Not Meet"), "gray", "did_not_meet,=,1"];
		if (doc.auto_repeat) return [__("Repeats"), "blue", "auto_repeat,=,1"];
		if (doc.publish) return [__("Published"), "blue", "publish,=,1"];
	},
};
