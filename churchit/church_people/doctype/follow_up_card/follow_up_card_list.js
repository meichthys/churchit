// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Follow-up Card"] = {
	add_fields: ["status", "due_on", "snoozed_until"],
	get_indicator(doc) {
		if (doc.status === "Closed") return [__("Closed"), "gray", "status,=,Closed"];
		if (doc.snoozed_until) return [__("Snoozed"), "blue", "snoozed_until,is,set"];
		if (doc.due_on && doc.due_on < frappe.datetime.get_today()) {
			return [__("Overdue"), "red", `status,=,Open|due_on,<,${frappe.datetime.get_today()}`];
		}
		return [__("Open"), "orange", "status,=,Open"];
	},
};
