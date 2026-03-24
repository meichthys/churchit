frappe.query_reports["Fund Transactions By Date"] = {
	filters: [
		...church.get_church_report_filters(),
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			mandatory: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			mandatory: 1,
		},
	],

	onload: function (report) {
		church.setup_church_report(report);
	},
};
