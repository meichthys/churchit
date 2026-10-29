// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Form Response", {
	refresh(frm) {
		const recorders = ["Church Finance", "Church Manager"];
		if (frm.doc.payment_status === "Paid" && frappe.user.has_role(recorders)) {
			frm.add_custom_button(__("Record Refund"), () =>
				frappe.confirm(__("Record that the payment was refunded?"), () =>
					frm.call("record_refund").then(() => frm.reload_doc())
				)
			);
		}
	},
});
