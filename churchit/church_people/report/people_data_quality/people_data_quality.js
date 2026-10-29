// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["People Data Quality"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "problem",
			label: __("Problem"),
			fieldtype: "Select",
			options: [
				"",
				"No Way to Reach",
				"Invalid Email",
				"Invalid Phone Number",
				"Email Bounced",
				"Mail Returned",
				"Possible Duplicate",
				"Child Without Birth Date",
				"No Family",
			].map((value) => ({ value, label: value && __(value) })),
		},
	],
};
