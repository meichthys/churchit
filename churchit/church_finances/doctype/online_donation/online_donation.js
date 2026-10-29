// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Online Donation", {
	refresh(frm) {
		if (frm.doc.status !== "Pending" || !frappe.user.has_role("Church Finance")) return;
		frm.add_custom_button(__("Record Charged Gift"), () =>
			frm.call("record_charged_gift").then(() => frm.reload_doc())
		);
	},
});
