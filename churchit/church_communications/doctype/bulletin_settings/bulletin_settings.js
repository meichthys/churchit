// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Bulletin Settings", {
	refresh(frm) {
		lock_shared_settings(frm);
	},
});

// The server refuses what a church may not change (church_access.refuse_changing_shared_settings):
// a user who does not work across every church changes only their own church's sections row.
function lock_shared_settings(frm) {
	if (frm.doc.__onload?.has_every_church !== false) return;
	for (const df of frm.meta.fields) {
		if (df.fieldname !== "church_sections") frm.set_df_property(df.fieldname, "read_only", 1);
	}
	frm.set_query("church", "church_sections", () => ({
		filters: { name: ["in", frappe.boot.churchit.churches] },
	}));
	frm.set_intro(
		__(
			"These settings apply to every church. Only someone who works across every church can change them. Add or change the row of your own church under Sections Per Church."
		),
		"blue"
	);
}
