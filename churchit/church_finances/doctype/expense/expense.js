// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Expense", {
	setup(frm) {
		frm.set_query("vendor", () => ({ filters: { is_active: 1 } }));
	},

	refresh(frm) {
		const can_suggest =
			frm.doc.docstatus === 0 &&
			!frm.doc.missionary &&
			(frappe.user.has_role("Church Finance") || frappe.user.has_role("Church Manager")) &&
			churchit.ai.can_run();
		if (can_suggest)
			frm.add_custom_button(__("Suggest Type"), () => suggest_expense_type(frm));
	},

	vendor(frm) {
		if (!frm.doc.vendor) return;
		frappe.db.get_value("Vendor", frm.doc.vendor, "default_expense_type").then((r) => {
			const default_type = r && r.message && r.message.default_expense_type;
			if (default_type) frm.set_value("type", default_type);
		});
	},

	type(frm) {
		if (!frm.doc.type) {
			frm.set_value("associated_fund", null);
			return;
		}
		frappe.db.get_value("Expense Type", frm.doc.type, "fund").then((r) => {
			frm.set_value("associated_fund", (r && r.message && r.message.fund) || null);
		});
	},
});

// Suggest Type (church_finances/ai.py): one of the church's Expense Types from the vendor and the notes,
// filled unsaved. A new expense sends its church, vendor and notes; a saved one its name.
function suggest_expense_type(frm) {
	if (!frm.is_new() && frm.is_dirty()) {
		frappe.msgprint(__("Save the expense first, so the AI reads its vendor and notes."));
		return;
	}
	const { church, vendor, notes } = frm.doc;
	churchit.ai.run_action({
		title: __("Suggest Type"),
		method: "churchit.church_finances.ai.suggest_expense_type",
		args: { expense: frm.is_new() ? JSON.stringify({ church, vendor, notes }) : frm.doc.name },
		// The answer names its church; an answer for another church shows the fixed error of run_action.
		render: ({ church, type }) => {
			const is_other_church =
				!frappe.boot.churchit?.single_church &&
				frm.doc.church &&
				church !== frm.doc.church;
			if (is_other_church) throw new Error("another church");
			return churchit.ai.paragraphs([__("Expense Type: {0}", [type])]);
		},
		on_use: ({ type }) => frm.set_value("type", type),
		use_label: __("Use This Type"),
	});
}
