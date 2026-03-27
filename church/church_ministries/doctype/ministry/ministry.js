// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ministry", {
	refresh(frm) {
		if (frm.doc.publish) {
			frm.set_intro('🌐 This ministry is published to the public website', 'blue');
		}
	},
});
