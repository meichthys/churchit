frappe.query_reports["Person Donations"] = {
	filters: [
		{
			fieldname: "person",
			label: __("Person"),
			fieldtype: "Link",
			options: "Person",
		},
	],

};
