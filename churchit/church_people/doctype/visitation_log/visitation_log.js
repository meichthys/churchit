// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Visitation Log", {
	schedule_follow_up(frm) {
		frappe.new_doc("Visitation Log", {
			person: frm.doc.person,
			visit_type: frm.doc.visit_type,
			visited_by: frm.doc.visited_by,
			status: "Scheduled",
		});
	},
});
