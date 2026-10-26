// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["Function Registrations"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "function",
			label: __("Function"),
			fieldtype: "Link",
			options: "Function",
			description: __("Choose a function to see a column for each of its questions."),
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Pending", "Confirmed", "Waitlisted", "Cancelled"],
		},
	],
};
