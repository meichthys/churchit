// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Check-In Settings", {
	refresh(frm) {
		frm.set_query("name_tag_format", () => ({
			filters: { doc_type: "Function Check-In", raw_printing: 0 },
		}));
		frm.set_query("zpl_format", () => ({
			filters: { doc_type: "Function Check-In", raw_printing: 1 },
		}));
		frm.add_custom_button(__("Print Test Tag"), () => print_test_tag(frm));
		frm.add_custom_button(__("Open Check-In Station"), () =>
			frappe.set_route("check-in"),
		);
		lock_shared_settings(frm);
	},
});

// The server refuses what a church may not change (church_access.refuse_changing_shared_settings):
// a user who does not work across every church changes only their own church's printer row.
function lock_shared_settings(frm) {
	if (frm.doc.__onload?.has_every_church !== false) return;
	for (const df of frm.meta.fields) {
		if (df.fieldname !== "printers")
			frm.set_df_property(df.fieldname, "read_only", 1);
	}
	frm.set_query("church", "printers", () => ({
		filters: { name: ["in", frappe.boot.churchit.churches] },
	}));
	frm.set_intro(
		__(
			"These settings apply to every church. Only someone who works across every church can change them. Add or change the row of your own church under Printers Per Church.",
		),
		"blue",
	);
}

function print_test_tag(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the settings first, then print a test tag."));
		return;
	}
	frappe.prompt(
		{
			fieldtype: "Link",
			fieldname: "person",
			label: __("Person"),
			options: "Person",
			reqd: 1,
		},
		(values) => church.name_tags.print_for({ persons: [values.person] }),
		__("Print Test Tag"),
		__("Print"),
	);
}
