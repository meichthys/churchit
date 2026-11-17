frappe.query_reports["Inactive Members"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "threshold_days",
			label: __("Inactive Threshold (Days)"),
			fieldtype: "Int",
			default: 60,
		},
	],
	onload: function (report) {
		const filter = report.get_filter("threshold_days");
		filter.$input.attr("title", filter.df.label);
	},
};
