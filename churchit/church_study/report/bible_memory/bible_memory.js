frappe.query_reports["Bible Memory"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "memorized",
			label: __("Memorized"),
			fieldtype: "Select",
			options: "\nYes\nNo",
			default: "Yes",
		},
		{
			fieldname: "user",
			label: __("User"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "group",
			label: __("Group"),
			fieldtype: "Link",
			options: "Group",
		},
	],
};
