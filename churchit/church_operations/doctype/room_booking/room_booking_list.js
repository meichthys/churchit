// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// The calendar view extends the list view, so the room diary starts without these too.
frappe.listview_settings["Room Booking"] = {
	filters: [["status", "not in", ["Denied", "Cancelled"]]],
};
