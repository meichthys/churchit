// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Church AI Suggestion", {
	refresh(frm) {
		if (!frm.doc.reference_doctype || !frm.doc.reference_name) return;
		frm.add_custom_button(__("Open Request"), () =>
			frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name)
		).addClass("btn-primary");
	},
});
