frappe.query_reports["Visitor Log"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "days",
			label: __("Visitor Window (Days)"),
			fieldtype: "Int",
			default: 60,
		},
	],
	onload: function (report) {
		const filter = report.get_filter("days");
		filter.$input.attr("title", filter.df.label);
	},
};
