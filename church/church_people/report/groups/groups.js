frappe.query_reports["Groups"] = {
	filters: [
		...church.get_church_report_filters(),
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nActive\nInactive",
		},
		{
			fieldname: "from_date",
			label: __("Created From"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("Created To"),
			fieldtype: "Date",
		},
	],

	formatter: function (value, row, column, data) {
		if (!data || !value) return value;
		if (column.fieldname === "group_name") {
			return `<a href="/app/group/${encodeURIComponent(data.name)}">${frappe.utils.escape_html(value)}</a>`;
		}
		if (column.fieldname === "church") {
			return `<a href="/app/church/${encodeURIComponent(value)}">${frappe.utils.escape_html(value)}</a>`;
		}
		return value;
	},

	onload: function (report) {
		church.setup_church_report(report);
	},
};
