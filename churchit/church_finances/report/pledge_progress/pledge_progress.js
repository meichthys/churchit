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

	formatter: function (value, row, column, data, default_formatter) {
		// A pledge has no goal of its own: a blank cell reads better than a zero goal.
		if (data && data.person && column.fieldname === "goal_amount")
			return "";
		return default_formatter(value, row, column, data);
	},
};
