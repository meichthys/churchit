// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["Assimilation Funnel"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "from_date",
			label: __("First Visit From"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("First Visit To"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "weeks",
			label: __("Came Back Within (Weeks)"),
			fieldtype: "Int",
			default: 8,
			reqd: 1,
		},
	],
};
