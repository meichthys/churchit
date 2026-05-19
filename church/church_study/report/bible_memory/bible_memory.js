frappe.query_reports["Bible Memory"] = {
	filters: [
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
	],
};
