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
};
