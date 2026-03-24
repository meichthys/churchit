frappe.query_reports["Function Count by Type"] = {
	filters: [
		...church.get_church_report_filters(),
		{
			fieldname: "start",
			label: __("Start Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "end",
			label: __("End Date"),
			fieldtype: "Date",
		},
	],

	onload: function (report) {
		church.setup_church_report(report);
	},
};
