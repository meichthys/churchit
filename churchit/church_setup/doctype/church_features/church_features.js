// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Church Features", {
	refresh(frm) {
		// One row per shipped page, kept in step with the app on every migrate.
		frm.set_df_property("website_pages", "cannot_add_rows", true);
		frm.set_df_property("website_pages", "cannot_delete_rows", true);
		frm.saved_switches = get_switches(frm);
		frm.saved_multi_church = cint(frm.doc.enable_multi_church);

		// The server refuses the save (church_access.refuse_changing_shared_settings); this says so up front.
		if (frm.doc.__onload?.has_every_church === false) {
			frm.disable_form();
			frm.set_intro(
				__(
					"Church Features apply to every church. Only someone who works across every church can change them."
				),
				"blue"
			);
		}
	},
	enable_multi_church(frm) {
		// The switch cannot be turned off again once a branch exists, so ask before the tick stays.
		if (!frm.doc.enable_multi_church || frm.saved_multi_church) return;
		frappe.confirm(
			__(
				"Turn on Multi-Church? When you save, every existing record gets the main church and every existing user is limited to it. You cannot turn it off again while branch churches exist."
			),
			null,
			() => frm.set_value("enable_multi_church", 0)
		);
	},
	after_save(frm) {
		// The dock and sidebars come from the cached bootinfo, so the desk keeps
		// showing the old set until it is reloaded. Website page rows do not change them.
		if (get_switches(frm) === frm.saved_switches) return;
		frappe.confirm(
			__("Settings that change the desk were saved. Reload now to apply them?"),
			() => window.location.reload()
		);
	},
});

function get_switches(frm) {
	// The module, multi-church and privacy checks. The public website switch does not change the desk.
	return frm.meta.fields
		.filter((df) => df.fieldtype === "Check" && df.fieldname !== "disable_public_website")
		.map((df) => cint(frm.doc[df.fieldname]))
		.join();
}
