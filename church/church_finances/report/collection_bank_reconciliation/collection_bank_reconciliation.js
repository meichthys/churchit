frappe.query_reports["Collection Bank Reconciliation"] = {
	filters: [
		...church.get_church_report_filters(),
		{
			fieldname: "parent_filter",
			label: __("Collections"),
			fieldtype: "Link",
			options: "Collection",
			mandatory: 1,
		},
	],

	onload: function (report) {
		church.setup_church_report(report);
	},
};
