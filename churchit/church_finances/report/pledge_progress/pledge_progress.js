// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["Pledge Progress"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "campaign",
			label: __("Campaign"),
			fieldtype: "Link",
			options: "Pledge Campaign",
		},
	],
};
