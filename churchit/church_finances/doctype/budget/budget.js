// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Budget", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Budget vs Actual"), () => {
				frappe.route_options = { budget: frm.doc.name };
				frappe.set_route("query-report", "Budget vs Actual");
			}, __("View"));
			render_status(frm);
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

function render_status(frm) {
	frm.call("get_progress").then((r) => {
		const progress = r.message;
		const wrapper = frm.get_field("status_html").$wrapper;
		if (!progress || !progress.rows.length) {
			wrapper.html(
				`<p class="text-muted">${__("Add expense lines to see spending against this budget.")}</p>`
			);
			return;
		}
		wrapper.html(_status_html(progress));
	});
}

function _status_html(progress) {
	const rows = progress.rows;
	const budgeted = rows.reduce((sum, row) => sum + row.budgeted, 0);
	const actual = rows.reduce((sum, row) => sum + row.actual, 0);
	const over = rows.filter((row) => row.actual > row.budgeted);

	return `
		<div class="row" style="margin-bottom: 15px;">
			${_headline(__("Period Elapsed"), `${Math.round(progress.elapsed_fraction * 100)}%`)}
			${_headline(__("Budget Used"), budgeted ? `${Math.round((actual / budgeted) * 100)}%` : "-")}
			${_headline(__("Spent of Budgeted"), `${format_currency(actual)} / ${format_currency(budgeted)}`)}
			${_headline(__("Lines Over Budget"), over.length)}
		</div>
		<table class="table table-bordered" style="margin: 0;">
			<tbody>${rows.map(_status_row).join("")}</tbody>
		</table>`;
}

function _headline(label, value) {
	return `
		<div class="col-sm-3">
			<div class="text-muted small">${label}</div>
			<div class="bold">${value}</div>
		</div>`;
}

function _status_row(row) {
	const over = row.actual > row.budgeted;
	return `
		<tr>
			<td style="width: 30%;">${frappe.utils.escape_html(row.expense_type || "")}</td>
			<td class="text-right" style="width: 25%;">
				${format_currency(row.actual)} / ${format_currency(row.budgeted)}
			</td>
			<td>
				<div class="progress" style="height: 8px; margin: 6px 0;">
					<div class="progress-bar ${over ? "bg-danger" : "bg-success"}"
						style="width: ${Math.min(row.pct, 100)}%"></div>
				</div>
			</td>
			<td class="text-right" style="width: 10%;">${Math.round(row.pct)}%</td>
			<td style="width: 15%;">
				<span class="indicator-pill ${over ? "red" : "green"}">
					${frappe.utils.escape_html(row.status)}
				</span>
			</td>
		</tr>`;
}
