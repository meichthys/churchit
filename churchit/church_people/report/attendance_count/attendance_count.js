// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["Attendance Count"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "from_date",
			label: __("Since"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			fieldname: "to_date",
			label: __("Until"),
			fieldtype: "Date",
		},
		{
			fieldname: "min_times",
			label: __("At Least (Times)"),
			fieldtype: "Int",
			default: 1,
		},
		{
			fieldname: "function_type",
			label: __("Function Type"),
			fieldtype: "Link",
			options: "Function Type",
		},
	],
};
