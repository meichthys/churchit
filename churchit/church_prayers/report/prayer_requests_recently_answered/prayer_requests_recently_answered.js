frappe.query_reports["Prayer Requests Recently Answered"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "request_since",
			label: __("Requests Since..."),
			fieldtype: "Date",
			mandatory: 1,
		},
	],
};
