// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Care Assignment"] = {
	hide_name_column: true,
	hide_name_filter: true,
	add_fields: ["start_date", "end_date"],
	get_indicator(doc) {
		const today = frappe.datetime.get_today();
		if (doc.end_date && doc.end_date < today) {
			return [__("Ended"), "gray", "end_date,is,set|end_date,<,Today"];
		}
		if (doc.start_date > today) {
			return [__("Upcoming"), "blue", "start_date,>,Today"];
		}
		return [__("Current"), "green", "start_date,<=,Today|end_date,is,not set"];
	},
};
