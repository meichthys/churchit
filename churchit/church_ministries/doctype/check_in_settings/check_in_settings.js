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
		frm.add_custom_button(__("Open Check-In Station"), () => frappe.set_route("check-in"));
	},
});

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
		__("Print")
	);
}
