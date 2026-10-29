// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Communication Consent", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.set_intro(
			__("A consent cannot be changed. If the person changes their mind, record it again."),
			"blue"
		);
		if (frappe.model.can_create("Communication Consent")) {
			frm.add_custom_button(__("Record a Change of Mind"), () =>
				frappe.new_doc("Communication Consent", {
					person: frm.doc.person,
					channel: frm.doc.channel,
					purpose: frm.doc.purpose,
					status: frm.doc.status === "Given" ? "Withdrawn" : "Given",
				})
			);
		}
	},
});
