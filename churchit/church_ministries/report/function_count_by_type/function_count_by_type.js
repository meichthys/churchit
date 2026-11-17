frappe.query_reports["Function Count by Type"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "start",
			label: __("Start Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "end",
			label: __("End Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
};
