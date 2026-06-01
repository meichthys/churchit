frappe.query_reports["First-Time Givers"] = {
	filters: [
		{
			fieldname: "window_days",
			label: __("Window (Days)"),
			fieldtype: "Int",
			default: 90,
		},
	],
};
