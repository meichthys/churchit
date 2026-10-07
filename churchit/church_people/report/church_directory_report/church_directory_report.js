frappe.query_reports["Church Directory Report"] = {
	hide_name_column: true,

	after_datatable_render: function () {
		const self = frappe.query_reports["Church Directory Report"];
		setTimeout(function () {
			$(".report-wrapper").hide();
			if (self._report) {
				self._refresh_preview(self._report);
			}
		}, 0);
	},

	_directory_args: function (report) {
		return {
			members_only: report.get_filter_value("members_only") ? 1 : 0,
			group_by_family: report.get_filter_value("group_by_family") ? 1 : 0,
			show_photos: report.get_filter_value("show_photos") ? 1 : 0,
			show_roles: report.get_filter_value("show_roles") ? 1 : 0,
			show_membership: report.get_filter_value("show_membership") ? 1 : 0,
			show_hoh: report.get_filter_value("show_hoh") ? 1 : 0,
			show_church_image: report.get_filter_value("show_church_image") ? 1 : 0,
			show_birthdays: report.get_filter_value("show_birthdays") ? 1 : 0,
			show_anniversaries: report.get_filter_value("show_anniversaries") ? 1 : 0,
			show_missionaries: report.get_filter_value("show_missionaries") ? 1 : 0,
			blank_back_cover: report.get_filter_value("blank_back_cover") ? 1 : 0,
			show_page_numbers: report.get_filter_value("show_page_numbers") ? 1 : 0,
			include_notes_page: report.get_filter_value("include_notes_page") ? 1 : 0,
			booklet_printing: report.get_filter_value("booklet_printing") ? 1 : 0,
			church: report.get_filter_value("church") || null,
		};
	},

	_refresh_preview: function (report) {
		const args = this._directory_args(report);
		frappe.call({
			method: "churchit.church_people.report.church_directory_report.church_directory_report.get_directory_html",
			args: args,
			callback: function (r) {
				if (!r.message) return;
				if (!report._$preview) {
					report._$preview = $(
						'<iframe style="width:100%;height:80vh;border:none;display:block;"></iframe>'
					).insertAfter($(".report-wrapper"));
					report._$booklet_note = $(
						'<p class="text-muted small" style="padding: 0 var(--padding-md);"></p>'
					)
						.text(
							__(
								"To print the booklet, print double-sided and flip on the short edge. Keep the sheets in order, then fold the stack in half with the cover on the outside."
							)
						)
						.insertBefore(report._$preview);
				}
				report._$booklet_note.toggle(Boolean(args.booklet_printing));
				report._$preview[0].srcdoc = r.message;
			},
		});
	},

	filters: [
		...church.report_filters(),
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
			fieldname: "show_church_image",
			label: __("Show Church Image"),
			fieldtype: "Check",
			default: 0,
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
		{
			fieldname: "blank_back_cover",
			label: __("Blank Back Cover"),
			fieldtype: "Check",
			default: 0,
			depends_on: "eval:!doc.booklet_printing",
		},
		{
			fieldname: "show_page_numbers",
			label: __("Show Page Numbers"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "include_notes_page",
			label: __("Include Notes Page"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "booklet_printing",
			label: __("Booklet Printing"),
			fieldtype: "Check",
			default: 0,
		},
	],

	onload: function (report) {
		frappe.query_reports["Church Directory Report"]._report = report;

		report.page.add_inner_button(__("Print Directory"), function () {
			const args = frappe.query_reports["Church Directory Report"]._directory_args(report);
			window.open(
				"/api/method/churchit.church_people.report.church_directory_report.church_directory_report.download_directory_pdf?" +
					$.param(args)
			);
		});
	},
};
