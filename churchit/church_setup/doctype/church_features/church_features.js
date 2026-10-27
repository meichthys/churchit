// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Church Features", {
	refresh(frm) {
		// One row per shipped page, kept in step with the app on every migrate.
		frm.set_df_property("website_pages", "cannot_add_rows", true);
		frm.set_df_property("website_pages", "cannot_delete_rows", true);
		frm.saved_switches = get_switches(frm);
	},
	after_save(frm) {
		// The dock and sidebars come from the cached bootinfo, so the desk keeps
		// showing the old set until it is reloaded. Website page rows do not change them.
		if (get_switches(frm) === frm.saved_switches) return;
		frappe.confirm(__("Module visibility has changed. Reload now to apply it?"), () =>
			window.location.reload()
		);
	},
});

function get_switches(frm) {
	// The module, multi-church and privacy checks.
	return frm.meta.fields
		.filter((df) => df.fieldtype === "Check")
		.map((df) => cint(frm.doc[df.fieldname]))
		.join();
}
