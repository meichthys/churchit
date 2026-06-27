// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bible Memory Item", {
	refresh(frm) {
		// The User field is locked by default so people only manage their own
		// passages. Managers/Administrators may reassign it from the Desk.
		const can_reassign =
			frappe.user_roles.includes("Church Manager") ||
			frappe.user_roles.includes("System Manager");
		frm.set_df_property("user", "read_only", can_reassign ? 0 : 1);
	},
});
