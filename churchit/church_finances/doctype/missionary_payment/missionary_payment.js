frappe.ui.form.on("Missionary Payment", {
	refresh(frm) {
		if (frm.doc.status === "Approved") {
			frm.add_custom_button(__("Mark as Sent"), () => {
				let d = new frappe.ui.Dialog({
					title: __("Mark Missionary Payment as Sent"),
					fields: [
						{
							label: __("Reference Number"),
							fieldname: "reference",
							fieldtype: "Data",
							reqd: 1,
							default: frm.doc.reference
						}
					],
					primary_action_label: __("Submit"),
					primary_action(values) {
						frappe.call({
							method: "churchit.church_finances.doctype.missionary_payment.missionary_payment.mark_as_sent",
							args: {
								name: frm.doc.name,
								reference: values.reference
							},
							callback: function(r) {
								if (!r.exc) {
									frm.reload_doc();
									d.hide();
								}
							}
						});
					}
				});
				d.show();
			}, __("Actions"));
		}

		if (frm.doc.status === "Sent") {
			frm.add_custom_button(__("Reconcile"), () => {
				let d = new frappe.ui.Dialog({
					title: __("Reconcile Missionary Payment"),
					fields: [
						{
							label: __("Bank Transaction Reference"),
							fieldname: "reference",
							fieldtype: "Data",
							reqd: 1,
							default: frm.doc.reference
						}
					],
					primary_action_label: __("Reconcile"),
					primary_action(values) {
						frappe.call({
							method: "churchit.church_finances.doctype.missionary_payment.missionary_payment.reconcile",
							args: {
								name: frm.doc.name,
								reference: values.reference
							},
							callback: function(r) {
								if (!r.exc) {
									frm.reload_doc();
									d.hide();
								}
							}
						});
					}
				});
				d.show();
			}, __("Actions"));
		}
	}
});
