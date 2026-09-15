// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Budget", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(
				__("Budget vs Actual"),
				() => {
					frappe.route_options = { budget: frm.doc.name };
					frappe.set_route("query-report", "Budget vs Actual");
				},
				__("View")
			);
			load_progress(frm);
		}

		frm.fields_dict["lines"].grid.add_custom_button(__("Add All Expense Types"), () => {
			frm.call("add_all_expense_types").then((r) => {
				const added = r.message;
				if (added > 0) {
					frm.refresh_field("lines");
					frm.refresh_field("budgeted_amount");
					frappe.show_alert({
						message: __("{0} expense type(s) added", [added]),
						indicator: "green",
					});
				} else {
					frappe.show_alert({
						message: __("All expense types already added"),
						indicator: "blue",
					});
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

function load_progress(frm) {
	frm.call("get_progress").then((r) => {
		const rows = (r.message && r.message.rows) || [];
		populate_actuals(frm, rows);
		render_status(frm, rows);
	});
}

function populate_actuals(frm, rows) {
	if (!(frm.doc.lines || []).length) return;
	const actual_by_type = Object.fromEntries(rows.map((row) => [row.expense_type, row.actual]));
	(frm.doc.lines || []).forEach((line) => {
		line.actual = actual_by_type[line.expense_type] || 0;
	});
	frm.refresh_field("lines");
}

function render_status(frm, rows) {
	const wrapper = frm.get_field("status_html").$wrapper;
	if (!rows.length) {
		wrapper.html(
			`<p class="text-muted">${__(
				"Add expense lines to see spending against this budget."
			)}</p>`
		);
		return;
	}
	const budgeted = frm.doc.budgeted_amount || 0;
	const actual = rows.reduce((sum, row) => sum + row.actual, 0);
	const pct = budgeted ? Math.round((actual / budgeted) * 100) : 0;
	wrapper.html(`
		<div class="row" style="margin-bottom: 15px;">
			${_headline(__("Total Actual"), format_currency(actual))}
			${_headline(__("% Budget Used"), `${pct}%`)}
			${_headline(__("Remaining Amount"), format_currency(budgeted - actual))}
		</div>`);
}

function _headline(label, value) {
	return `
		<div class="col-sm-4">
			<div class="text-muted small">${label}</div>
			<div class="bold">${value}</div>
		</div>`;
}
