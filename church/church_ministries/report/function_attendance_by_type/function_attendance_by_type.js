frappe.query_reports["Function Attendance by Type"] = {
	filters: [
		...church.get_church_report_filters(),
	],

	onload: function (report) {
		church.setup_church_report(report);
	},
};
