frappe.query_reports["Person Positions Ending This Month"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), 60),
		},
	],
	onload: function (report) {
		report.page_title = __("Positions Ending");
		report.page.set_title(report.page_title);
	},
};
