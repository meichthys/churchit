frappe.query_reports["New Members Last 90 Days"] = {
	filters: [
		{
			fieldname: "days",
			label: __("Days Back"),
			fieldtype: "Int",
			default: 90,
		},
	],
};
