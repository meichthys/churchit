// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Family", {
	setup(frm) {
		frm.set_query("primary_contact", () => ({
			filters: { name: ["in", (frm.doc.members || []).map((row) => row.member)] },
		}));
	},
	refresh(frm) {
		if (!frm.is_new()) {
			add_merge_menu_item(frm);
		}
	},
});

// A merge deletes this family, so it needs the right to delete.
function add_merge_menu_item(frm) {
	if (!frappe.model.can_delete("Family")) return;
	const name = frappe.utils.escape_html(frm.doc.family_name);
	frm.page.add_menu_item(__("Merge Into…"), () => {
		const dialog = new frappe.ui.Dialog({
			title: __("Merge {0} Into Another Family", [name]),
			fields: [
				{
					fieldname: "keep",
					fieldtype: "Link",
					options: "Family",
					label: __("Family to Keep"),
					reqd: 1,
					get_query: () => ({ filters: { name: ["!=", frm.doc.name] } }),
					description: __(
						"The members of {0} and everything that names it move to this family, and {0} is deleted. This family keeps its own details and gets the ones it does not have from {0}. You cannot undo a merge.",
						[name]
					),
				},
			],
			primary_action_label: __("Merge"),
			primary_action({ keep }) {
				dialog.hide();
				frappe
					.call({
						method: "churchit.church_people.merge.merge_families",
						args: { keep, remove: frm.doc.name },
						freeze: true,
						freeze_message: __("Merging…"),
					})
					.then(() => frappe.set_route("Form", "Family", keep));
			},
		});
		dialog.show();
	});
}
