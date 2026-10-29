// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["Group Attendance"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "group_type",
			label: __("Group Type"),
			fieldtype: "Link",
			options: "Group Type",
		},
		{
			fieldname: "group",
			label: __("Group"),
			fieldtype: "Link",
			options: "Group",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -84),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
	],
};
