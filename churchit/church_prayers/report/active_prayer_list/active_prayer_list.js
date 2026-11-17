frappe.query_reports["Active Prayer List"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "visibility",
			label: __("Shared With"),
			fieldtype: "Select",
			options: ["", "Whole Church", "Prayer Team", "Private"],
		},
	],
};
