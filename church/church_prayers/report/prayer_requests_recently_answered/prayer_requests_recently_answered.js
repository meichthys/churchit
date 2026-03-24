frappe.query_reports["Prayer Requests: Recently Answered"] = {
	filters: [
		...church.get_church_report_filters(),
		{
			fieldname: "request_since",
			label: __("Requests Since..."),
			fieldtype: "Date",
			mandatory: 1,
		},
	],

	onload: function (report) {
		church.setup_church_report(report);
	},
};
