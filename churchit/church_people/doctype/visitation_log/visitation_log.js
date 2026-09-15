// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

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
