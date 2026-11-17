frappe.query_reports["People"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "person_name",
			label: __("Name"),
			fieldtype: "Data",
		},
		{
			fieldname: "family",
			label: __("Family"),
			fieldtype: "Link",
			options: "Family",
		},
		{
			fieldname: "role",
			label: __("Role"),
			fieldtype: "Link",
			options: "Position Type",
		},
		{
			fieldname: "is_member",
			label: __("Active Member"),
			fieldtype: "Check",
		},
		{
			fieldname: "is_baptized",
			label: __("Baptized"),
			fieldtype: "Check",
		},
	],
};
