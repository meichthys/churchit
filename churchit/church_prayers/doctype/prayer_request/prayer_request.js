// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Prayer Request", {
	refresh(frm) {
		if (frm.doc.visibility === "Private") {
			frm.set_intro(
				__("This request is private. Do not share it with the prayer team or the church."),
				"yellow"
			);
		} else if (frm.doc.visibility === "Prayer Team") {
			frm.set_intro(
				__("Only the prayer team may see this request. Do not share it with the church."),
				"blue"
			);
		}
	},
	onload: function (frm) {
		// Filter recipient_type to DocTypes in the church app
		church.set_church_doctype_query(frm, "recipient_type");

		if (frm.is_new()) {
			// Pre-populate the requestor field with the current user's name
			frappe.db.get_value("Person", { user: frappe.session.user }, "name").then((r) => {
				if (r && r.message) {
					frm.set_value("requestor", r.message.name);
				}
			});
			// Set default status
			if (!frm.doc.status) {
				frappe.db
					.get_value("Prayer Request Status", { status: "Requested" }, "name")
					.then((r) => {
						if (r && r.message) {
							frm.set_value("status", r.message.name);
						}
					});
			}
		}
	},
});
