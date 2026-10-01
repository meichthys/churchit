frappe.query_reports["Collection Bank Reconciliation"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "parent_filter",
			label: __("Collections"),
			fieldtype: "Link",
			options: "Collection",
			mandatory: 1,
		},
	],
};
