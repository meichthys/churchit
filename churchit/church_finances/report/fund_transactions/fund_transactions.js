frappe.query_reports["Fund Transactions"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			mandatory: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			mandatory: 1,
		},
	],
};
