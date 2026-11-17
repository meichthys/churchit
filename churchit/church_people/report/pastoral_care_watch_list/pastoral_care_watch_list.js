frappe.query_reports["Pastoral Care Watch List"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "window_days",
			label: __("Window (Days)"),
			fieldtype: "Int",
			default: 30,
		},
	],
	onload: function (report) {
		const filter = report.get_filter("window_days");
		filter.$input.attr("title", filter.df.label);
	},
};
