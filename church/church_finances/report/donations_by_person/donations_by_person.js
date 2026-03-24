frappe.query_reports["Donations by Person"] = {
	filters: [
		...church.get_church_report_filters(),
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
	],

	onload: function (report) {
		church.setup_church_report(report);
	},
};
