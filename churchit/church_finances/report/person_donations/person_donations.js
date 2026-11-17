frappe.query_reports["Person Donations"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "person",
			label: __("Person"),
			fieldtype: "Link",
			options: "Person",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.year_start(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
};
