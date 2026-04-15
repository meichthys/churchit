frappe.query_reports["Function Attendance by Person"] = {
	filters: [
		{
			fieldname: "person",
			label: __("Person"),
			fieldtype: "Link",
			options: "Person",
		},
		{
			fieldname: "function_type",
			label: __("Function Type"),
			fieldtype: "Link",
			options: "Function Type",
		},
		{
			fieldname: "start",
			label: __("Start Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "end",
			label: __("End Date"),
			fieldtype: "Date",
		},
	],

};
