frappe.query_reports["Collection Bank Reconciliation"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "parent_filter",
			label: __("Collection"),
			fieldtype: "Link",
			options: "Collection",
			mandatory: 1,
			get_query: () => ({ filters: { docstatus: ["<", 2] } }),
		},
	],

	onload: function (report) {
		if (report.get_filter_value("parent_filter")) return;
		frappe.db
			.get_list("Collection", {
				filters: { docstatus: 1 },
				fields: ["name"],
				order_by: "date desc",
				limit: 1,
			})
			.then((rows) => {
				if (rows.length)
					report.set_filter_value("parent_filter", rows[0].name);
			});
	},
};
