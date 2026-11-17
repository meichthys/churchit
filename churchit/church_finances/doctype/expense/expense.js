// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Expense", {
	setup(frm) {
		frm.set_query("vendor", () => ({ filters: { is_active: 1 } }));
	},

	onload(frm) {
		set_type_query(frm);
	},

	church(frm) {
		set_type_query(frm);
	},

	refresh(frm) {
		show_projected_balance(frm);
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

// Expense Types are shared by every church, but each takes its money from one fund, which has to be this
// church's or a shared one (Expense.validate). Offer only the types that use such a fund.
function set_type_query(frm) {
	const church_name =
		church.is_multi_church() && (frm.doc.church || frappe.boot.churchit.church);
	if (!church_name) return;
	frappe.db
		.get_list("Fund", { filters: { church: ["in", [church_name, ""]] }, limit: 0 })
		.then((funds) => {
			const names = funds.map((fund) => fund.name);
			frm.set_query("type", () => ({ filters: { fund: ["in", names] } }));
		});
}

// The approver submits a saved draft, so the form shows them the warning that the requester saw on save.
function show_projected_balance(frm) {
	const { docstatus, associated_fund, amount } = frm.doc;
	if (frm.is_new() || docstatus !== 0 || !associated_fund || !amount) return;
	frappe.db.get_value("Fund", associated_fund, ["fund", "balance"]).then(({ message }) => {
		const balance = (message.balance || 0) - amount;
		if (balance >= 0) return;
		frm.dashboard.set_headline_alert(
			__("Submitting this expense will reduce the {0} fund balance to {1}.", [
				frappe.utils.escape_html(message.fund),
				frappe.format(balance, { fieldtype: "Currency" }, { inline: true }),
			]),
			"orange"
		);
	});
}

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
