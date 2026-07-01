frappe.query_reports["Collection Bank Reconciliation"] = {
	filters: [
		{
			fieldname: "parent_filter",
			label: __("Collections"),
			fieldtype: "Link",
			options: "Collection",
			mandatory: 1,
		},
	],

};
