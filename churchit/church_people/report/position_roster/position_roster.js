frappe.query_reports["Position Roster"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "only_active",
			label: __("Active Only"),
			fieldtype: "Check",
			default: 1,
		},
	],
};
