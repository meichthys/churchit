frappe.query_reports["Person Donations"] = {
	filters: [
		...church.get_church_report_filters(),
		{
			fieldname: "person",
			label: __("Person"),
			fieldtype: "Link",
			options: "Person",
		},
	],

	onload: function (report) {
		church.setup_church_report(report);
	},
};
