frappe.query_reports["New Members Last 90 Days"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "days",
			label: __("Days Back"),
			fieldtype: "Int",
			default: 90,
		},
	],
	onload: function (report) {
		report.page_title = __("New Members");
		report.page.set_title(report.page_title);

		const filter = report.get_filter("days");
		filter.$input.attr("title", filter.df.label);
	},
};
