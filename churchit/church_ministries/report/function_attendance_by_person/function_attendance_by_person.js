frappe.query_reports["Function Attendance by Person"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "person",
			label: __("Person"),
			fieldtype: "Link",
			options: "Person",
		},
		{
			fieldname: "function_type",
			label: __("Function Type"),
			fieldtype: "Link",
			options: "Function Type",
		},
		{
			fieldname: "group",
			label: __("Group"),
			fieldtype: "Link",
			options: "Group",
		},
		{
			fieldname: "start",
			label: __("Start Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			fieldname: "end",
			label: __("End Date"),
			fieldtype: "Date",
		},
	],
};
