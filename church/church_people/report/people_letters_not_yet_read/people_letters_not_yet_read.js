frappe.query_reports["People Letters Not Yet Read"] = {
	filters: [
		...church.get_church_report_filters(),
	],

	onload: function (report) {
		church.setup_church_report(report);
	},
};
