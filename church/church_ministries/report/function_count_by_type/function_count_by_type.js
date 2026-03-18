frappe.query_reports["Function Count by Type"] = {
	filters: [
		{
			fieldname: "church",
			label: __("Church"),
			fieldtype: "Link",
			options: "Church",
		},
		{
			fieldname: "start",
			label: __("Start Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "end",
			label: __("End Date"),
			fieldtype: "Date",
		},
	],

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
