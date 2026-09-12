// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.views.calendar["Function"] = {
	field_map: {
		start: "start_date",
		end: "end_date",
		id: "name",
		title: "title",
		allDay: "all_day",
	},
	get_events_method: "frappe.desk.calendar.get_events",
};
