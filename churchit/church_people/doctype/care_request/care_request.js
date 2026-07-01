// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Care Request", {
	person(frm) {
		if (!frm.doc.person || frm.doc.assigned_to) return;
		// If the person has a current care assignment, pre-fill Assigned To
		// with their assigned deacon. An assignment is current when it has
		// started and has no end date (or the end date is in the future).
		const today = frappe.datetime.nowdate();
		frappe.db.get_list("Care Assignment", {
			filters: { person: frm.doc.person, start_date: ["<=", today] },
			fields: ["deacon", "end_date"],
			order_by: "start_date desc",
			limit: 1,
		}).then((rows) => {
			if (!rows || !rows.length) return;
			const row = rows[0];
			if (row.deacon && (!row.end_date || row.end_date >= today)) {
				frm.set_value("assigned_to", row.deacon);
			}
		});
	},
});
