// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["Personal Data Due for Removal"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "due_by",
			label: __("Due By"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), 30),
			reqd: 1,
		},
	],
};
