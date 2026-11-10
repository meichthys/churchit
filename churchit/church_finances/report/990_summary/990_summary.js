frappe.query_reports["990 Summary"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: new Date().getFullYear(),
			reqd: 1,
		},
	],
};
