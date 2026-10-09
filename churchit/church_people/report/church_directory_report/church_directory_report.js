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
		const args = { church: report.get_filter_value("church") || null };
		for (const filter of report.filters) {
			if (filter.df.fieldtype !== "Check") continue;
			args[filter.df.fieldname] = filter.get_value() ? 1 : 0;
		}
		return args;
	},

	// Lays the check filters out in labelled columns, one per `group`.
	_group_options: function (report) {
		const $options = $(`<div class="directory-options">
			<style>
				.directory-options { display: flex; flex-wrap: wrap; gap: var(--margin-md) 40px; width: 100%; padding: var(--padding-sm) 0; }
				.directory-options .directory-option-heading { font-size: var(--text-sm); font-weight: 600; color: var(--text-muted); margin-bottom: var(--margin-xs); }
				#page-query-report .directory-options .frappe-control { width: auto; max-width: none; padding: 0; margin: 0; }
				.directory-options .checkbox { margin: 0; }
				.directory-options .checkbox label { padding: 1px 0; }
				.directory-options .help-box { display: none; }
			</style>
		</div>`).appendTo(report.page.page_form);
		const groups = {};
		for (const filter of report.filters) {
			const group = filter.df.group;
			if (!group) continue;
			if (!groups[group]) {
				groups[group] = $('<div class="directory-option-group"></div>')
					.append($('<div class="directory-option-heading"></div>').text(group))
					.appendTo($options);
			}
			groups[group].append(filter.wrapper);
		}
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
			group: __("People"),
		},
		{
			fieldname: "group_by_family",
			label: __("Group by Family"),
			fieldtype: "Check",
			default: 1,
			group: __("People"),
		},
		{
			fieldname: "show_photos",
			label: __("Photos"),
			fieldtype: "Check",
			default: 0,
			group: __("Show"),
		},
		{
			fieldname: "show_roles",
			label: __("Positions"),
			fieldtype: "Check",
			default: 0,
			group: __("Show"),
		},
		{
			fieldname: "show_membership",
			label: __("Membership Status"),
			fieldtype: "Check",
			default: 1,
			group: __("Show"),
		},
		{
			fieldname: "show_hoh",
			label: __("Head of Household"),
			fieldtype: "Check",
			default: 1,
			group: __("Show"),
		},
		{
			fieldname: "show_phone",
			label: __("Phone Numbers"),
			fieldtype: "Check",
			default: 1,
			group: __("Contact Details"),
		},
		{
			fieldname: "show_email",
			label: __("Emails"),
			fieldtype: "Check",
			default: 1,
			group: __("Contact Details"),
		},
		{
			fieldname: "show_address",
			label: __("Addresses"),
			fieldtype: "Check",
			default: 1,
			group: __("Contact Details"),
		},
		{
			fieldname: "show_birthdays",
			label: __("Birthday List"),
			fieldtype: "Check",
			default: 0,
			group: __("Extra Pages"),
		},
		{
			fieldname: "show_anniversaries",
			label: __("Anniversary List"),
			fieldtype: "Check",
			default: 0,
			group: __("Extra Pages"),
		},
		{
			fieldname: "show_missionaries",
			label: __("Missionaries"),
			fieldtype: "Check",
			default: 0,
			group: __("Extra Pages"),
		},
		{
			fieldname: "include_notes_page",
			label: __("Notes Page"),
			fieldtype: "Check",
			default: 0,
			group: __("Extra Pages"),
		},
		{
			fieldname: "show_church_image",
			label: __("Church Image on Cover"),
			fieldtype: "Check",
			default: 0,
			group: __("Printing"),
		},
		{
			fieldname: "show_page_numbers",
			label: __("Page Numbers"),
			fieldtype: "Check",
			default: 0,
			group: __("Printing"),
		},
		{
			fieldname: "booklet_printing",
			label: __("Booklet"),
			fieldtype: "Check",
			default: 0,
			group: __("Printing"),
		},
		{
			fieldname: "blank_back_cover",
			label: __("Blank Back Cover"),
			fieldtype: "Check",
			default: 0,
			group: __("Printing"),
			depends_on: "eval:!doc.booklet_printing",
		},
	],

	onload: function (report) {
		frappe.query_reports["Church Directory Report"]._report = report;
		frappe.query_reports["Church Directory Report"]._group_options(report);

		report.page.add_inner_button(__("Print Directory"), function () {
			const args = frappe.query_reports["Church Directory Report"]._directory_args(report);
			window.open(
				"/api/method/churchit.church_people.report.church_directory_report.church_directory_report.download_directory_pdf?" +
					$.param(args)
			);
		});
	},
};
