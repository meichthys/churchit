frappe.query_reports["Function Attendance by Type"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "group",
			label: __("Group"),
			fieldtype: "Link",
			options: "Group",
		},
	],
};
