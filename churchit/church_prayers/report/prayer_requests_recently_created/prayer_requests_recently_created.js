frappe.query_reports["Prayer Requests Recently Created"] = {
	filters: [
		{
			fieldname: "request_since",
			label: __("Requests Since..."),
			fieldtype: "Date",
			mandatory: 1,
		},
	],

};
