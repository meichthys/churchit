frappe.query_reports["Person Anniversaries This Month"] = {
	filters: [...church.report_filters()],
	// An anniversary with No Year shows its month and day only, because its year is made up.
	formatter(value, row, column, data, default_formatter) {
		if (
			column.fieldname === "anniversary" &&
			value &&
			data?.anniversary_year_unknown
		)
			return new Intl.DateTimeFormat(frappe.boot.lang, {
				month: "long",
				day: "numeric",
				timeZone: "UTC",
			}).format(new Date(value));
		return default_formatter(value, row, column, data);
	},
};
