frappe.query_reports["Function Attendance by Type"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "group",
			label: __("Group"),
			fieldtype: "Link",
			options: "Group",
		},
	],
	onload: function (report) {
		report.page_title = __("Check-Ins by Function");
		report.page.set_title(report.page_title);
	},
};
