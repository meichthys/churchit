from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import escape_html

from churchit.church_finances.doctype.budget.budget import COMPARISON_WINDOWS, get_current_budget
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = filters or {}
	budget_name = filters.get("budget") or get_current_budget()
	if not budget_name:
		return get_columns(None), [], _("No budget found. Create a budget to track spending against it.")

	comparison = filters.get("comparison")
	if comparison not in COMPARISON_WINDOWS:
		comparison = None

	progress = frappe.get_doc("Budget", budget_name).get_progress(comparison)
	columns = get_columns(comparison)
	data = progress["rows"]
	set_report_link_titles(columns, data)
	return columns, data, get_message(budget_name, progress)


def get_columns(comparison):
	columns = [
		{
			"fieldname": "expense_type",
			"fieldtype": "Link",
			"options": "Expense Type",
			"label": _("Expense Type"),
			"width": 220,
		},
		{"fieldname": "budgeted", "fieldtype": "Currency", "label": _("Budgeted"), "width": 120},
		{
			"fieldname": "expected_to_date",
			"fieldtype": "Currency",
			"label": _("Expected to Date"),
			"width": 150,
		},
		{"fieldname": "actual", "fieldtype": "Currency", "label": _("Actual"), "width": 120},
		{"fieldname": "pending", "fieldtype": "Currency", "label": _("Pending"), "width": 110},
		{"fieldname": "variance", "fieldtype": "Currency", "label": _("Budget Remaining"), "width": 150},
		{"fieldname": "pct", "fieldtype": "Percent", "label": _("% Used"), "width": 90},
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
			"width": 150,
		},
	]


def get_message(budget_name, progress):
	link = f'<a href="/app/budget/{quote(budget_name)}">{escape_html(budget_name)}</a>'
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
