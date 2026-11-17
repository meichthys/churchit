frappe.query_reports["Church Attendance"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -28),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "function",
			label: __("Function"),
			fieldtype: "Link",
			options: "Function",
		},
		{
			fieldname: "group",
			label: __("Group"),
			fieldtype: "Link",
			options: "Group",
		},
	],
};
