frappe.query_reports["Church Directory Report"] = {
	hide_name_column: true,

	after_datatable_render: function() {
		const self = frappe.query_reports["Church Directory Report"];
		setTimeout(function() {
			$('.report-wrapper').hide();
			if (self._report) {
				self._refresh_preview(self._report);
			}
		}, 0);
	},

	_refresh_preview: function(report) {
		const args = {
			members_only: report.get_filter_value('members_only') ? 1 : 0,
			group_by_family: report.get_filter_value('group_by_family') ? 1 : 0,
			show_photos: report.get_filter_value('show_photos') ? 1 : 0,
			show_roles: report.get_filter_value('show_roles') ? 1 : 0,
			show_membership: report.get_filter_value('show_membership') ? 1 : 0,
			show_hoh: report.get_filter_value('show_hoh') ? 1 : 0,
			show_birthdays: report.get_filter_value('show_birthdays') ? 1 : 0,
			show_anniversaries: report.get_filter_value('show_anniversaries') ? 1 : 0,
			show_missionaries: report.get_filter_value('show_missionaries') ? 1 : 0,
		};

		frappe.call({
			method: 'churchit.church_people.report.church_directory_report.church_directory_report.get_directory_html',
			args: args,
			callback: function(r) {
				if (!r.message) return;
				if (!report._$preview) {
					report._$preview = $('<iframe style="width:100%;height:80vh;border:none;display:block;"></iframe>')
						.insertAfter($('.report-wrapper'));
				}
				report._$preview[0].srcdoc = r.message;
			}
		});
	},

	filters: [
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

	onload: function(report) {
		frappe.query_reports["Church Directory Report"]._report = report;

		report.page.add_inner_button(__('Print Directory'), function() {
			const self = frappe.query_reports["Church Directory Report"];
			if (self._report && self._report._$preview) {
				self._report._$preview[0].contentWindow.print();
			}
		});
	},
};
