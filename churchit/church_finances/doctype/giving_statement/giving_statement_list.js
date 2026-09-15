// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Giving Statement"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Generate Statements"), () => {
			const year = new Date().getFullYear() - 1;
			frappe.prompt(
				[
					{
						fieldname: "from_date",
						fieldtype: "Date",
						label: __("From Date"),
						reqd: 1,
						default: `${year}-01-01`,
					},
					{
						fieldname: "to_date",
						fieldtype: "Date",
						label: __("To Date"),
						reqd: 1,
						default: `${year}-12-31`,
					},
				],
				(values) => {
					frappe.call({
						method: "churchit.church_finances.doctype.giving_statement.giving_statement.generate_statements",
						args: values,
						freeze: true,
						freeze_message: __("Building statements..."),
						callback: (r) => {
							const { created = 0, updated = 0 } = r.message || {};
							frappe.msgprint({
								title: __("Statements Ready"),
								indicator: "green",
								message: __("{0} created, {1} rebuilt.", [created, updated]),
							});
							listview.refresh();
						},
					});
				},
				__("Generate Statements"),
				__("Generate")
			);
		});
	},
};
