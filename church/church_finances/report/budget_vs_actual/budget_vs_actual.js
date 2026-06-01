frappe.query_reports["Budget vs Actual"] = {
	filters: [
		{
			fieldname: "budget",
			label: __("Budget"),
			fieldtype: "Link",
			options: "Budget",
		},
	],
};
