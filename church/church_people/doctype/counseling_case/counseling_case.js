// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Counseling Case", {
	sessions_add(frm, cdt, cdn) {
		// Default a new session's counselor to the case's counselor.
		if (frm.doc.counselor) {
			frappe.model.set_value(cdt, cdn, "counselor", frm.doc.counselor);
		}
	},
});
