frappe.query_reports["Fund Balances"] = {
	filters: [
		...church.get_church_report_filters(),
	],

	onload: function (report) {
		church.setup_church_report(report);
	},
};
