import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import getdate, nowdate

from churchit.query import Date


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"fieldname": "expense_type", "fieldtype": "Link", "options": "Expense Type", "label": "Expense Type", "width": 220},
		{"fieldname": "budgeted", "fieldtype": "Currency", "label": "Budgeted", "width": 130},
		{"fieldname": "expected_to_date", "fieldtype": "Currency", "label": "Expected to Date", "width": 150},
		{"fieldname": "actual", "fieldtype": "Currency", "label": "Actual", "width": 130},
		{"fieldname": "variance", "fieldtype": "Currency", "label": "Budget Remaining", "width": 150},
		{"fieldname": "pct", "fieldtype": "Percent", "label": "% Used", "width": 100},
	]


def get_data(filters):
	budget_name = filters.get("budget")
	if not budget_name:
		return []

	budget = frappe.get_doc("Budget", budget_name)
	start = getdate(budget.start_date)
	end = getdate(budget.end_date)
	today = getdate(nowdate())

	# fraction of the budget period elapsed (clamped 0–1)
	total_days = (end - start).days
	elapsed_days = (min(today, end) - start).days
	elapsed_fraction = (elapsed_days / total_days) if total_days > 0 else 1.0
	elapsed_fraction = max(0.0, min(1.0, elapsed_fraction))

	actuals = _get_actuals(str(start), str(end))

	rows = []
	for line in budget.lines or []:
		et = line.expense_type
		budgeted = line.budgeted_amount or 0
		expected_to_date = budgeted * elapsed_fraction
		actual = actuals.get(et, 0)
		variance = budgeted - actual
		pct = (actual / budgeted * 100) if budgeted else 0
		rows.append({
			"expense_type": et,
			"budgeted": budgeted,
			"expected_to_date": expected_to_date,
			"actual": actual,
			"variance": variance,
			"pct": pct,
		})

	rows.sort(key=lambda r: r["expense_type"] or "")
	return rows


def _get_actuals(start, end):
	Expense = frappe.qb.DocType("Expense")
	rows = (
		frappe.qb.from_(Expense)
		.select(Expense.type.as_("expense_type"), Sum(Expense.amount).as_("total"))
		.where((Expense.docstatus == 1) & Date(Expense.date)[start:end])
		.groupby(Expense.type)
		.run(as_dict=True)
	)
	return {r.expense_type: float(r.total or 0) for r in rows}
