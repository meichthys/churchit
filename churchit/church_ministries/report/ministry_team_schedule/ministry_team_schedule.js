// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["Ministry Team Schedule"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), 28),
			reqd: 1,
		},
		{
			fieldname: "ministry",
			label: __("Ministry"),
			fieldtype: "Link",
			options: "Ministry",
		},
		{
			fieldname: "function",
			label: __("Function"),
			fieldtype: "Link",
			options: "Function",
		},
		{
			fieldname: "only_open",
			label: __("Only Open Positions"),
			fieldtype: "Check",
		},
	],
};
