frappe.query_reports["Visitation Followups Needed"] = {
	filters: [...church.report_filters()],
	onload: function (report) {
		report.page_title = __("Follow-ups Needed");
		report.page.set_title(report.page_title);
	},
};
