// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["Pathway Progress"] = {
	filters: [
		{
			fieldname: "pathway",
			label: __("Pathway"),
			fieldtype: "Link",
			options: "Pathway",
			reqd: 1,
		},
	],

	onload: function (report) {
		if (report.get_filter_value("pathway")) return;
		frappe.db
			.get_list("Pathway", {
				fields: ["name"],
				order_by: "pathway_name asc",
				limit: 1,
			})
			.then((rows) => {
				if (rows.length)
					report.set_filter_value("pathway", rows[0].name);
			});
	},
};
