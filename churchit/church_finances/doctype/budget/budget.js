// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Budget", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Budget vs Actual"), () => {
				frappe.route_options = { budget: frm.doc.name };
				frappe.set_route("query-report", "Budget vs Actual");
			}, __("View"));
		}

		frm.fields_dict["lines"].grid.add_custom_button(__("Add All Expense Types"), () => {
			frm.call("add_all_expense_types").then((r) => {
				const added = r.message;
				if (added > 0) {
					frm.refresh_field("lines");
					frm.refresh_field("budgeted_amount");
					frappe.show_alert({ message: __("{0} expense type(s) added", [added]), indicator: "green" });
				} else {
					frappe.show_alert({ message: __("All expense types already added"), indicator: "blue" });
				}
			});
		});
	},
});

frappe.ui.form.on("Budget Line", {
	budgeted_amount(frm) {
		_update_total(frm);
	},
	lines_remove(frm) {
		_update_total(frm);
	},
});

function _update_total(frm) {
	const total = (frm.doc.lines || []).reduce((s, r) => s + (r.budgeted_amount || 0), 0);
	frm.set_value("budgeted_amount", total);
}
