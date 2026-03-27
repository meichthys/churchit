frappe.query_reports["Ministries"] = {
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
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "fund",
			label: __("Fund"),
			fieldtype: "Link",
			options: "Fund",
		},
		{
			fieldname: "publish",
			label: __("Published"),
			fieldtype: "Select",
			options: "\nYes\nNo",
		},
	],

	formatter: function (value, row, column, data) {
		if (!data || !value) return value;
		if (column.fieldname === "ministry_name") {
			return `<a href="/app/ministry/${encodeURIComponent(data.name)}">${frappe.utils.escape_html(value)}</a>`;
		}
		if (column.fieldname === "church") {
			return `<a href="/app/church/${encodeURIComponent(value)}">${frappe.utils.escape_html(value)}</a>`;
		}
		if (column.fieldname === "group") {
			return `<a href="/app/group/${encodeURIComponent(value)}">${frappe.utils.escape_html(value)}</a>`;
		}
		if (column.fieldname === "publish") {
			return value ? __("Yes") : __("No");
		}
		return value;
	},

	onload: function (report) {
		church.setup_church_report(report);
	},
};
