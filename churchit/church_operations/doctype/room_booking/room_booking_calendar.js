// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.views.calendar["Room Booking"] = {
	field_map: {
		start: "start_datetime",
		end: "end_datetime",
		id: "name",
		title: "purpose",
	},
	get_events_method: "frappe.desk.calendar.get_events",
};
