// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["Ministry Team Schedule"] = {
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
			default: frappe.datetime.add_days(frappe.datetime.get_today(), 28),
			reqd: 1,
		},
		{ fieldname: "ministry", label: __("Ministry"), fieldtype: "Link", options: "Ministry" },
		{ fieldname: "function", label: __("Function"), fieldtype: "Link", options: "Function" },
		{ fieldname: "only_open", label: __("Only Open Positions"), fieldtype: "Check" },
	],

	onload(report) {
		if (!frappe.model.can_create("Ministry Team Assignment")) return;
		report.page.add_inner_button(__("Fill Open Needs"), () => this.fill_open_needs(report));
	},

	// The Ministry Team Grid report has the same button.
	fill_open_needs(report) {
		const filters = report.get_filter_values();
		const [method, args] = filters.function
			? ["fill_open_needs", { function: filters.function, ministry: filters.ministry }]
			: [
					"fill_open_needs_between",
					{
						from_date: filters.from_date,
						to_date: filters.to_date,
						ministry: filters.ministry,
						church: filters.church,
					},
			  ];
		frappe.confirm(
			__(
				"Ask people from each position's roster to fill the open places? The daily job sends them the requests."
			),
			() =>
				frappe.call({
					method: `churchit.church_ministries.auto_schedule.${method}`,
					args: args,
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
