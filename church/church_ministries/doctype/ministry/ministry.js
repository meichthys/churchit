// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ministry", {
	refresh(frm) {
		if (frm.doc.publish) {
			frm.set_intro('🌐 This ministry is published to the public website', 'blue');
		}
	},

	create_recurring_function(frm) {
		if (frm.is_new()) {
			frappe.msgprint(__("Please save this Ministry before creating a recurring function."));
			return;
		}
		frappe.new_doc("Function", {
			associated_ministry: frm.doc.name,
			auto_repeat: 1,
		});
	},
});
