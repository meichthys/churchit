frappe.query_reports["Budget vs Actual"] = {
	filters: [
		{
			fieldname: "budget",
			label: __("Budget"),
			fieldtype: "Link",
			options: "Budget",
			description: __("Leave blank to use the budget covering today"),
		},
		{
			fieldname: "comparison",
			label: __("Compare With"),
			fieldtype: "Select",
			options: [
				"",
				"Same Period Last Year",
				"Last Month",
				"Last Quarter",
				"Last 12 Months",
			].join("\n"),
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "status" && data && data.status) {
			const indicator = data.actual > data.budgeted ? "red" : "green";
			value = `<span class="indicator-pill ${indicator}">${value}</span>`;
		}
		return value;
	},
};
