// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

const STATEMENT_METHODS =
	"churchit.church_finances.doctype.giving_statement.giving_statement";

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
	hide_name_column: true,
	hide_name_filter: true,
	add_fields: ["emailed_on", "email"],
	get_indicator(doc) {
		if (doc.emailed_on)
			return [__("Emailed"), "green", "emailed_on,is,set"];
		if (!doc.email) return [__("No Email"), "red", "email,is,not set"];
		return [__("Not Sent"), "orange", "emailed_on,is,not set|email,is,set"];
	},
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
							const {
								created = 0,
								updated = 0,
								removed = 0,
								emailed_uncovered = 0,
							} = r.message || {};
							const lines = [];
							if (!created && !updated) {
								lines.push(
									__(
										"No gifts with a named giver to a tax-deductible fund between {0} and {1}. Check the dates, or the Tax Deductible box on the funds.",
										[
											frappe.datetime.str_to_user(
												values.from_date,
											),
											frappe.datetime.str_to_user(
												values.to_date,
											),
										],
									),
								);
							} else {
								lines.push(
									__("{0} created, {1} rebuilt.", [
										created,
										updated,
									]),
								);
							}
							if (removed) {
								lines.push(
									__(
										"{0} statements that no giver needs any more were deleted.",
										[removed],
									),
								);
							}
							if (emailed_uncovered) {
								lines.push(
									__(
										"{0} statements that no giver needs any more stay, because they were emailed.",
										[emailed_uncovered],
									),
								);
							}
							frappe.msgprint({
								title:
									created || updated
										? __("Statements Ready")
										: __("No Statements Made"),
								indicator:
									created || updated ? "green" : "orange",
								message: lines.join("<br>"),
							});
							listview.refresh();
						},
					});
				},
				__("Generate Statements"),
				__("Generate"),
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
							const {
								queued = 0,
								no_email = 0,
								already_emailed = 0,
							} = r.message || {};
							frappe.msgprint({
								title: queued
									? __("Emails Queued")
									: __("Nothing to Email"),
								indicator: queued ? "green" : "orange",
								message: __(
									"{0} will be emailed, {1} have no email address, {2} were already emailed.",
									[queued, no_email, already_emailed],
								),
							});
						},
					});
				},
				__("Email Statements"),
				__("Email"),
			);
		});
	},
};
