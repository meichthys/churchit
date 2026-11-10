frappe.query_reports["Variance"] = {
	filters: [...church.report_filters()],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.variance_flagged == 1) {
			return `<span style="color: red; font-weight: bold;">${value}</span>`;
		}
		return value;
	},
};
