// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Function Check-In", {
	setup(frm) {
		// A recurring template takes no check-ins: its occurrences do.
		frm.set_query("function", () => ({ filters: { auto_repeat: 0 } }));
	},

	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Print Name Tag"), () => {
			church.name_tags.print_for({ check_ins: [frm.doc.name] });
		});
	},
});
