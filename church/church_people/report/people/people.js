frappe.query_reports["People"] = {
	filters: [
		...church.get_church_report_filters(),
		{
			fieldname: "person_name",
			label: __("Name"),
			fieldtype: "Data",
		},
		{
			fieldname: "family",
			label: __("Family"),
			fieldtype: "Link",
			options: "Family",
		},
		{
			fieldname: "role",
			label: __("Role"),
			fieldtype: "Link",
			options: "Position Type",
		},
		{
			fieldname: "is_member",
			label: __("Member"),
			fieldtype: "Check",
		},
		{
			fieldname: "is_baptized",
			label: __("Baptized"),
			fieldtype: "Check",
		},
	],

	formatter: function (value, row, column, data) {
		if (column.fieldname === "full_name" && data) {
			return `<a href="/app/person/${data.name}">${frappe.utils.escape_html(value)}</a>`;
		}
		if (column.fieldname === "family_name" && data) {
			if (!data.family) return "";
			return `<a href="/app/family/${data.family}">${frappe.utils.escape_html(value)}</a>`;
		}
		if (column.fieldname === "roles" && !value) {
			return "";
		}
		if (column.fieldname === "is_member" || column.fieldname === "is_baptized") {
			return value ? __("Yes") : __("No");
		}
		return value;
	},

	onload: function (report) {
		church.setup_church_report(report);
	},
};
