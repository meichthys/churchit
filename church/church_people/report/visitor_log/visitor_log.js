frappe.query_reports["Visitor Log"] = {
	filters: [
		{
			fieldname: "days",
			label: __("Visitor Window (Days)"),
			fieldtype: "Int",
			default: 60,
		},
	],
};
