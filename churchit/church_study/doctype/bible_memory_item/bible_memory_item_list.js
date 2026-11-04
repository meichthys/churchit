// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Bible Memory Item"] = {
	hide_name_column: true,
	hide_name_filter: true,
	add_fields: ["memorized", "progress"],
	get_indicator(doc) {
		if (doc.memorized) return [__("Memorized"), "green", "memorized,=,1"];
		if (doc.progress > 0) return [__("In Progress"), "blue", "memorized,=,0|progress,>,0"];
		return [__("Not Started"), "gray", "progress,=,0"];
	},
	formatters: {
		progress: (value) => `${cint(value)}%`,
	},
	onload(listview) {
		if (!frappe.user.has_role(["Church Manager", "System Manager"])) return;
		listview.page.add_inner_button(__("Assign a Passage"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Assign a Passage"),
				fields: [
					{
						fieldname: "reference",
						fieldtype: "Data",
						label: __("Reference"),
						description: __("Such as John 3:16-18"),
						reqd: 1,
						bible_reference: 1,
					},
					{
						fieldname: "translation",
						fieldtype: "Link",
						label: __("Translation"),
						options: "Bible Translation",
						reqd: 1,
						get_query: () => ({ filters: { status: "Ready" } }),
					},
					{
						fieldname: "group",
						fieldtype: "Link",
						label: __("Group"),
						options: "Group",
						description: __("Everyone in the group who has a portal login."),
					},
					{
						fieldname: "user",
						fieldtype: "Link",
						label: __("User"),
						options: "User",
						get_query: () => ({ filters: { enabled: 1 } }),
					},
				],
				primary_action_label: __("Assign"),
				primary_action(values) {
					frappe
						.call({
							method: "churchit.church_study.doctype.bible_memory_item.bible_memory_item.assign_memory",
							args: {
								reference: values.reference,
								translation: values.translation,
								group: values.group,
								users: values.user ? [values.user] : [],
							},
							freeze: true,
						})
						.then(({ message }) => {
							dialog.hide();
							listview.refresh();
							frappe.show_alert({
								message: __("{0} assigned, {1} already had it.", [
									message.created,
									message.skipped,
								]),
								indicator: "green",
							});
							if (!message.missing_users.length) return;
							frappe.msgprint({
								title: __("Not assigned: no portal login"),
								indicator: "orange",
								message: message.missing_users.join("<br>"),
							});
						});
				},
			});
			dialog.show();
		});
	},
};
