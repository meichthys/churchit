frappe.query_reports["Ministries"] = {
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
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "publish",
			label: __("Published"),
			fieldtype: "Select",
			options: "\nYes\nNo",
		},
	],
};
