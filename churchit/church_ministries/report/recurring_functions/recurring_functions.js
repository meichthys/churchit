frappe.query_reports["Recurring Functions"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "associated_ministry",
			label: __("Ministry"),
			fieldtype: "Link",
			options: "Ministry",
		},
		{
			fieldname: "repeat_frequency",
			label: __("Frequency"),
			fieldtype: "Select",
			options: ["", "Daily", "Weekly", "Monthly", "Yearly"].join("\n"),
		},
	],
};
