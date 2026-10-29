frappe.query_reports["Church Attendance"] = {
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
