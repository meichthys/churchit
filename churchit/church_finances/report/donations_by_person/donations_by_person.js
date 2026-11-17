frappe.query_reports["Donations by Person"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.year_start(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		if (data && data.is_total_row) {
			if (column.fieldname === "person") return `<b>${__("Total")}</b>`;
			return `<b>${default_formatter(value, row, column, data)}</b>`;
		}
		return default_formatter(value, row, column, data);
	},
};
