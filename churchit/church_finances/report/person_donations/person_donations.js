frappe.query_reports["Person Donations"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "person",
			label: __("Person"),
			fieldtype: "Link",
			options: "Person",
		},
	],
};
