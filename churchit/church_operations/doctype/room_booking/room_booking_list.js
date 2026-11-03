// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// The calendar view extends the list view, so the room diary starts without these too.
// A filter on Requested would hide the approved bookings from the diary, so the queue is a report.
frappe.listview_settings["Room Booking"] = {
	// The setup sheet prints the booking number, so the ID filter stays.
	hide_name_column: true,
	filters: [["status", "not in", ["Denied", "Cancelled"]]],
};
