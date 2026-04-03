frappe.query_reports["Church Directory Report"] = {
	hide_name_column: true,
	filters: [
		{
			fieldname: "church",
			label: __("Church"),
			fieldtype: "Link",
			options: "Church",
			reqd: 1,
		},
		{
			fieldname: "include_sub_churches",
			label: __("Include Sub-Churches"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "members_only",
			label: __("Members Only"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "group_by_family",
			label: __("Group by Family"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_photos",
			label: __("Show Photos"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "show_roles",
			label: __("Show Positions"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "show_membership",
			label: __("Show Membership Status"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_hoh",
			label: __("Show Head of Household"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_birthdays",
			label: __("Include Birthday List"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "show_anniversaries",
			label: __("Include Anniversary List"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "show_missionaries",
			label: __("Include Missionaries"),
			fieldtype: "Check",
			default: 0,
		},

	],

	onload: function (report) {
		const default_church = frappe.defaults.get_user_default("church");
		if (default_church) {
			report.set_filter_value("church", default_church);
		}

		church._get_churches().then(churches => {
			report.page.fields_dict.church.toggle(churches.length > 1);
		});

		report.page.add_inner_button(__('Print Directory'), function () {
			const church = report.get_filter_value('church');
			const include_sub_churches = report.get_filter_value('include_sub_churches') ? 1 : 0;
			const members_only = report.get_filter_value('members_only') ? 1 : 0;
			const show_photos = report.get_filter_value('show_photos') ? 1 : 0;
			const show_roles = report.get_filter_value('show_roles') ? 1 : 0;
			const show_membership = report.get_filter_value('show_membership') ? 1 : 0;
			const show_hoh = report.get_filter_value('show_hoh') ? 1 : 0;
			const show_birthdays = report.get_filter_value('show_birthdays') ? 1 : 0;
			const show_anniversaries = report.get_filter_value('show_anniversaries') ? 1 : 0;
			const group_by_family = report.get_filter_value('group_by_family') ? 1 : 0;
			const show_missionaries = report.get_filter_value('show_missionaries') ? 1 : 0;

			if (!church) {
				frappe.msgprint(__('Please select a Church first.'));
				return;
			}

			frappe.call({
				method: 'church.church_people.report.church_directory_report.church_directory_report.get_directory_html',
				args: {
					church,
					include_sub_churches,
					members_only,
					group_by_family,
					show_photos,
					show_roles,
					show_membership,
					show_hoh,
					show_birthdays,
					show_anniversaries,
					show_missionaries,
				},
				freeze: true,
				freeze_message: __('Generating Church Directory\u2026'),
				callback: function (r) {
					if (!r.message) return;
					const win = window.open('', '_blank');
					win.document.open();
					win.document.write(r.message);
					win.document.close();
					// Allow images/fonts to load before triggering print
					win.addEventListener('load', function () {
						win.focus();
						win.print();
					});
				},
			});
		});
	},
};
