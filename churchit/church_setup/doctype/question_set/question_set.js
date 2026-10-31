// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Question Set", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.publish_as_form) {
			frm.add_web_link(
				`/form/new?question_set=${encodeURIComponent(frm.doc.name)}`,
				__("Open Form")
			);
		}
	},
});
