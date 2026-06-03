// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Meeting Minutes", {
	function(frm) {
		if (!frm.doc.function) return;
		frappe.db.get_doc("Function", frm.doc.function).then((fn) => {
			const attendance = fn.attendance || [];
			if (!attendance.length) {
				frappe.show_alert({ message: __("No attendees found on that function."), indicator: "orange" });
				return;
			}
			// Merge: add anyone not already in the attendees table
			const existing = new Set((frm.doc.attendees || []).map((r) => r.person));
			let added = 0;
			attendance.forEach((row) => {
				if (row.person && !existing.has(row.person)) {
					const child = frm.add_child("attendees");
					child.person = row.person;
					added++;
				}
			});
			if (added) {
				frm.refresh_field("attendees");
				frappe.show_alert({ message: __("{0} attendee(s) added from function.", [added]), indicator: "green" });
			} else {
				frappe.show_alert({ message: __("All function attendees are already listed."), indicator: "blue" });
			}
		});
	},
});
