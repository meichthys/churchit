// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Church", {
	refresh(frm) {
		if (frm.doc.publish) {
			frm.set_intro('🌐 This church is published to the public website', 'blue');
		}
	},
});
