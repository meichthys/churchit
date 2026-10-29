// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

const STATEMENT_METHODS = "churchit.church_finances.doctype.giving_statement.giving_statement";

function period_fields() {
	const year = new Date().getFullYear() - 1;
	return [
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
	];
}

frappe.listview_settings["Giving Statement"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Generate Statements"), () => {
			frappe.prompt(
				period_fields(),
				(values) => {
					frappe.call({
						method: `${STATEMENT_METHODS}.generate_statements`,
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

		listview.page.add_inner_button(__("Email Statements"), () => {
			frappe.prompt(
				[
					...period_fields(),
					{
						fieldname: "resend",
						fieldtype: "Check",
						label: __("Send again to statements already emailed"),
					},
				],
				(values) => {
					frappe.call({
						method: `${STATEMENT_METHODS}.email_statements`,
						args: values,
						freeze: true,
						callback: (r) => {
							frappe.msgprint({
								title: __("Emails Queued"),
								indicator: "green",
								message: __(
									"{0} statements are queued. A statement with no email address is skipped, and so is one already emailed unless you chose to send again.",
									[r.message || 0]
								),
							});
						},
					});
				},
				__("Email Statements"),
				__("Email")
			);
		});
	},
};
