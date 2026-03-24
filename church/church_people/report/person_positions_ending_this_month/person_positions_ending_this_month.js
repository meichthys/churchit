frappe.query_reports["Person Positions Ending This Month"] = {
	filters: [
		...church.get_church_report_filters(),
	],

	onload: function (report) {
		church.setup_church_report(report);
	},
};
