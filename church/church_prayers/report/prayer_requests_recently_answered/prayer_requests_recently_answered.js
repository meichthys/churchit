frappe.query_reports["Prayer Requests Recently Answered"] = {
	filters: [
		{
			fieldname: "request_since",
			label: __("Requests Since..."),
			fieldtype: "Date",
			mandatory: 1,
		},
	],

};
