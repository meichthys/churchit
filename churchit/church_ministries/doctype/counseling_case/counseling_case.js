// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Counseling Case", {
	sessions_add(frm, cdt, cdn) {
		// Default a new session's counselor to the case's counselor.
		if (frm.doc.counselor) {
			frappe.model.set_value(cdt, cdn, "counselor", frm.doc.counselor);
		}
	},
});
