// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Group Join Request", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status !== "Requested" || !frappe.model.can_write("Group"))
			return;
		for (const [label, approve] of [
			[__("Approve"), 1],
			[__("Deny"), 0],
		]) {
			frm.add_custom_button(label, () =>
				frappe
					.xcall("churchit.church_people.group_api.decide_join_request", {
						request: frm.doc.name,
						approve,
					})
					.then(() => frm.reload_doc())
			);
		}
	},
});
