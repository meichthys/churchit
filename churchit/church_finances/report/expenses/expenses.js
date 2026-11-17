frappe.query_reports["Expenses"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "type",
			label: __("Type"),
			fieldtype: "Link",
			options: "Expense Type",
		},
		{
			fieldname: "fund",
			label: __("Fund"),
			fieldtype: "Link",
			options: "Fund",
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		if (data && data.is_total_row) {
			if (column.fieldname === "name") return `<b>${__("Total")}</b>`;
			return `<b>${default_formatter(value, row, column, data)}</b>`;
		}
		return default_formatter(value, row, column, data);
	},
};
