// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["Pathway Progress"] = {
	filters: [
		{
			fieldname: "pathway",
			label: __("Pathway"),
			fieldtype: "Link",
			options: "Pathway",
			reqd: 1,
		},
	],
};
