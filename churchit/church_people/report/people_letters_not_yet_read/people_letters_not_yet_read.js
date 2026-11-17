frappe.query_reports["People Letters Not Yet Read"] = {
	filters: [
		{ fieldname: "from_date", fieldtype: "Date", label: __("From Date") },
		{ fieldname: "to_date", fieldtype: "Date", label: __("To Date") },
		...church.report_filters(),
	],
};
