// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Pledge Campaign", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(
			__("Pledge Progress"),
			() =>
				frappe.set_route("query-report", "Pledge Progress", {
					campaign: frm.doc.name,
				}),
			__("View"),
		);
	},
});
