// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Frappe's own Draft pill is red, the color of a failure. An unsubmitted record waits for staff.
frappe.listview_settings["Expense"] = {
	has_indicator_for_draft: true,
	has_indicator_for_cancelled: true,
	formatters: {
		// Date is a Datetime: show only the day, in the user's time zone as the form does.
		date(value) {
			const user_datetime =
				value && frappe.datetime.convert_to_user_tz(value);
			return frappe.datetime.str_to_user(user_datetime, false, true);
		},
	},
	get_indicator(doc) {
		if (doc.docstatus === 0)
			return [__("Pending"), "orange", "docstatus,=,0"];
		if (doc.docstatus === 1)
			return [__("Submitted"), "green", "docstatus,=,1"];
		return [__("Cancelled"), "gray", "docstatus,=,2"];
	},
};
