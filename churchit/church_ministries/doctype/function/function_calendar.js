// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

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
