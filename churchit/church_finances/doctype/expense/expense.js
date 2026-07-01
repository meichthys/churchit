// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Expense", {
	vendor(frm) {
		if (!frm.doc.vendor) return;
		frappe.db.get_value("Vendor", frm.doc.vendor, "default_expense_type").then((r) => {
			const default_type = r && r.message && r.message.default_expense_type;
			if (default_type) frm.set_value("type", default_type);
		});
	},

	type(frm) {
		if (!frm.doc.type) {
			frm.set_value("associated_fund", null);
			return;
		}
		frappe.db.get_value("Expense Type", frm.doc.type, "fund").then((r) => {
			frm.set_value("associated_fund", r && r.message && r.message.fund || null);
		});
	},
});
