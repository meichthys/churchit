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
};
