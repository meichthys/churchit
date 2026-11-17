from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import escape_html

from churchit.church_finances.doctype.church_budget.church_budget import (
	COMPARISON_WINDOWS,
	get_current_budget,
)
from churchit.utils import set_report_link_titles

AMOUNT_KEYS = (
	"budgeted",
	"expected_to_date",
	"actual",
	"pending",
	"variance",
	"comparison_budget",
	"comparison_actual",
)


def execute(filters=None):
	filters = filters or {}
	budget_name = filters.get("budget")
	if budget_name:
		# A report checks only its role, and a caller can name any church's budget.
		frappe.has_permission("Church Budget", doc=budget_name, throw=True)
	else:
		budget_name = get_current_budget(filters)
	if not budget_name:
		message = _("No budget found. Create a budget to track spending against it.")
		return get_columns(None), [], message, None

	comparison = filters.get("comparison")
	if comparison not in COMPARISON_WINDOWS:
		comparison = None

	progress = frappe.get_doc("Church Budget", budget_name).get_progress(comparison)
	columns = get_columns(comparison)
	data = progress["rows"]
	set_report_link_titles(columns, data)
	chart = get_chart(data)
	if data:
		data.append(get_total_row(data))
	return columns, data, get_message(budget_name, progress), chart


def get_total_row(rows):
	"""Sum the amounts and work out each percentage from the sums."""
	total = {"is_total_row": 1}
	for key in AMOUNT_KEYS:
		total[key] = sum(row[key] or 0 for row in rows)

	total["pct"] = get_percent(total["actual"], total["budgeted"])
	total["comparison_pct"] = get_percent(total["comparison_actual"], total["comparison_budget"])
	return total


def get_chart(rows):
	"""Budgeted, expected and actual for each expense type. The total row stays out, so it does not dwarf the
	lines."""
	if not rows:
		return None
	return {
		"data": {
			"labels": [row["expense_type"] for row in rows],
			"datasets": [
				{"name": label, "values": [row[key] or 0 for row in rows]}
				for key, label in (
					("budgeted", _("Budgeted")),
					("expected_to_date", _("Expected to Date")),
					("actual", _("Actual")),
				)
			],
		},
		"type": "bar",
		"fieldtype": "Currency",
	}


def get_percent(actual, budgeted):
	return round(actual / budgeted * 100, 1) if budgeted else 0


def get_columns(comparison):
	columns = [
		{
			"fieldname": "expense_type",
			"fieldtype": "Link",
			"options": "Expense Type",
			"label": _("Expense Type"),
			"width": 180,
		},
		{"fieldname": "budgeted", "fieldtype": "Currency", "label": _("Budgeted"), "width": 120},
		{
			"fieldname": "expected_to_date",
			"fieldtype": "Currency",
			"label": _("Expected to Date"),
			"width": 130,
		},
		{"fieldname": "actual", "fieldtype": "Currency", "label": _("Actual"), "width": 120},
		{"fieldname": "pending", "fieldtype": "Currency", "label": _("Pending"), "width": 110},
		{"fieldname": "variance", "fieldtype": "Currency", "label": _("Budget Remaining"), "width": 130},
		{"fieldname": "pct", "fieldtype": "Percent", "label": _("% Used"), "precision": 1, "width": 90},
		{"fieldname": "status", "fieldtype": "Data", "label": _("Status"), "width": 130},
	]
	if not comparison:
		return columns

	label = _(comparison)
	return [
		*columns,
		{
			"fieldname": "comparison_budget",
			"fieldtype": "Currency",
			"label": _("Budgeted ({0})").format(label),
			"width": 180,
		},
		{
			"fieldname": "comparison_actual",
			"fieldtype": "Currency",
			"label": _("Actual ({0})").format(label),
			"width": 180,
		},
		{
			"fieldname": "comparison_pct",
			"fieldtype": "Percent",
			"label": _("% Used ({0})").format(label),
			"precision": 1,
			"width": 150,
		},
	]


def get_message(budget_name, progress):
	link = f'<a href="/app/church-budget/{quote(budget_name)}">{escape_html(budget_name)}</a>'
	parts = [
		_("Budget: {0}").format(link),
		_("{0}% of the period elapsed").format(round(progress["elapsed_fraction"] * 100)),
	]
	window = progress.get("window")
	if window:
		parts.append(
			_("Compared with {0} ({1} to {2}), budgeted amounts prorated to that window").format(
				_(progress["comparison"]), window[0], window[1]
			)
		)
	return " &middot; ".join(parts)
