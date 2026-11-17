frappe.query_reports["YTD Giving by Person"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: new Date().getFullYear(),
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
