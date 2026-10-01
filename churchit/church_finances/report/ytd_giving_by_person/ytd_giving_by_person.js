frappe.query_reports["YTD Giving by Person"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: new Date().getFullYear(),
		},
	],
};
