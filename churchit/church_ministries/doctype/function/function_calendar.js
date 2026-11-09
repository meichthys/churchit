// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// The cell already shows the date, so an entry shows the name. The server adds each time to its date.
frappe.views.calendar["Function"] = {
	field_map: {
		start: "start_date",
		end: "end_date",
		id: "name",
		title: "function_name",
		allDay: "all_day",
	},
	get_events_method:
		"churchit.church_ministries.doctype.function.function.get_calendar_events",
	update_event_method:
		"churchit.church_ministries.doctype.function.function.move_on_calendar",
};
