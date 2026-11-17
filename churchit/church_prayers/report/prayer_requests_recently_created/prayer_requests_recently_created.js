frappe.query_reports["Prayer Requests Recently Created"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "request_since",
			label: __("Requests Since"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -30),
			mandatory: 1,
		},
	],
};
