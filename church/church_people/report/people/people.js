frappe.query_reports["People"] = {
	filters: [
		{
			fieldname: "church",
			label: __("Church"),
			fieldtype: "Link",
			options: "Church",
		},
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
		const default_church = frappe.defaults.get_user_default("church");
		if (default_church) {
			report.set_filter_value("church", default_church);
		}

		church._get_church_count().then(count => {
			report.page.fields_dict.church.toggle(count > 1);
		});
	},
};
