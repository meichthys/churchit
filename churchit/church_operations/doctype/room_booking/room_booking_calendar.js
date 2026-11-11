// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.views.calendar["Room Booking"] = {
	field_map: {
		start: "start_datetime",
		end: "end_datetime",
		id: "name",
		title: "purpose",
	},
	// Frappe orders a day's bookings by the list sort, which is newest first.
	// The list opens on this calendar, and Frappe's month grid is wider than a phone, so a phone opens on one day.
	options: {
		eventOrder: "start",
		...(frappe.is_mobile() && { initialView: "timeGridDay" }),
	},
	fields: ["status"],
	// The colors of the status pills, so a request that waits stands out from an approved booking.
	get_css_class(booking) {
		const state = frappe
			.get_meta("Room Booking")
			.states.find((row) => row.title === booking.status);
		return state?.color.toLowerCase();
	},
	get_events_method: "frappe.desk.calendar.get_events",
};
