frappe.query_reports["Groups"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nActive\nInactive",
		},
		{
			fieldname: "from_date",
			label: __("Created From"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("Created To"),
			fieldtype: "Date",
		},
	],
};
