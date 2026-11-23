// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Bible Memory Item", {
	setup(frm) {
		// Only a translation with readable text can be saved, as on /memorize.
		frm.translation_choices = frappe.xcall(
			"churchit.church_study.doctype.bible_memory_item.bible_memory_item.get_translation_choices",
			{},
			"GET",
		);
		frm.translation_choices.then(({ names }) =>
			frm.set_query("translation", () => ({
				filters: { name: ["in", names] },
			})),
		);
	},
	onload(frm) {
		// onload runs for every new item, setup only for the first form of the session.
		if (!frm.is_new()) return;
		frm.translation_choices.then(({ default: default_translation }) => {
			if (frm.is_new() && !frm.doc.translation && default_translation) {
				frm.set_value("translation", default_translation);
			}
		});
	},
	refresh(frm) {
		// The User field is locked by default so people only manage their own
		// passages. Managers/Administrators may reassign it from the Desk.
		const can_reassign =
			frappe.user_roles.includes("Church Manager") ||
			frappe.user_roles.includes("System Manager");
		frm.set_df_property("user", "read_only", can_reassign ? 0 : 1);
	},
});
