// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["Membership Changes"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -90),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "field",
			label: __("Field"),
			fieldtype: "Select",
			options: [
				"",
				{ value: "membership", label: __("Membership") },
				{ value: "membership_status", label: __("Status") },
			],
		},
		{
			fieldname: "value",
			label: __("New Value"),
			fieldtype: "Data",
		},
	],
};
