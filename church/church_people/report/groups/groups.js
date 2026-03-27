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
		if (column.fieldname === "group_name" && data) {
			return `<a href="/app/group/${encodeURIComponent(data.name)}">${frappe.utils.escape_html(value)}</a>`;
		}
		return value;
	},

	onload: function (report) {
		church.setup_church_report(report);
	},
};
