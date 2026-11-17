frappe.query_reports["Person Letters"] = {
	filters: [
		{ fieldname: "from_date", fieldtype: "Date", label: __("From Date") },
		{ fieldname: "to_date", fieldtype: "Date", label: __("To Date") },
		...church.report_filters(),
	],
};
