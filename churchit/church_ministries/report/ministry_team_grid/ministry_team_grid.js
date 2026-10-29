// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

const TEAM_GRID_COLORS = { Accepted: "green", Pending: "orange", Declined: "gray" };

frappe.query_reports["Ministry Team Grid"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), 56),
			reqd: 1,
		},
		{ fieldname: "ministry", label: __("Ministry"), fieldtype: "Link", options: "Ministry" },
	],

	formatter(value, row, column, data, default_formatter) {
		const cell = data && data._cells && data._cells[column.fieldname];
		if (!cell) return default_formatter(value, row, column, data);
		const escape = frappe.utils.escape_html;
		// The open places come first, so a narrow cell still shows them.
		const pills = cell.open
			? [
					`<a class="indicator-pill red team-grid-open" data-function="${escape(
						cell.function
					)}" data-position="${escape(data.position)}">${__("{0} open", [
						cell.open,
					])}</a>`,
			  ]
			: [];
		for (const person of cell.people) {
			pills.push(
				`<span class="indicator-pill ${TEAM_GRID_COLORS[person.status]}" title="${escape(
					__(person.status)
				)}">${escape(person.name)}</span>`
			);
		}
		return pills.join(" ");
	},

	onload(report) {
		$(report.page.wrapper)
			.off("click.team_grid")
			.on("click.team_grid", ".team-grid-open", (event) => {
				const { dataset } = event.currentTarget;
				frappe.new_doc("Ministry Team Assignment", {
					function: dataset.function,
					position: dataset.position,
				});
			});
		if (!frappe.model.can_create("Ministry Team Assignment")) return;
		report.page.add_inner_button(__("Fill Open Needs"), () => this.fill_open_needs(report));
	},

	// The Ministry Team Schedule report has the same button.
	fill_open_needs(report) {
		const filters = report.get_filter_values();
		frappe.confirm(
			__(
				"Ask people from each position's roster to fill the open places? The daily job sends them the requests."
			),
			() =>
				frappe.call({
					method: "churchit.church_ministries.auto_schedule.fill_open_needs_between",
					args: {
						from_date: filters.from_date,
						to_date: filters.to_date,
						ministry: filters.ministry,
						church: filters.church,
					},
					freeze: true,
					callback: ({ message }) => {
						const open = message.unfilled.reduce((total, row) => total + row.open, 0);
						frappe.show_alert(
							{
								message: __("Asked {0} people to serve. Places still open: {1}.", [
									message.assigned.length,
									open,
								]),
								indicator: open ? "orange" : "green",
							},
							10
						);
						report.refresh();
					},
				})
		);
	},
};
