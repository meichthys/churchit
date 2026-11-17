import frappe
from frappe import _
from frappe.utils import add_days, flt
from frappe.utils.nestedset import get_descendants_of
from pypika import Order

from churchit.church_scope import get_church_columns, scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = [*get_columns(), *get_church_columns(filters)]
	data = get_data(filters)
	set_report_link_titles(columns, data)
	if data:
		data.append(get_total_row(data))
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": _("Expense"), "options": "Expense", "width": 200},
		{
			"fieldname": "type",
			"fieldtype": "Link",
			"label": _("Type"),
			"options": "Expense Type",
			"width": 150,
		},
		{"fieldname": "notes", "fieldtype": "Data", "label": _("Notes"), "width": 200},
		{"fieldname": "date", "fieldtype": "Date", "label": _("Date"), "width": 120},
		{"fieldname": "amount", "fieldtype": "Currency", "label": _("Amount"), "width": 120},
		{"fieldname": "paid_on", "fieldtype": "Date", "label": _("Paid On"), "width": 120},
		{
			"fieldname": "payment_reference",
			"fieldtype": "Data",
			"label": _("Payment Reference"),
			"width": 150,
		},
	]


def get_total_row(rows):
	return frappe._dict(name=_("Total"), amount=sum(flt(row.amount) for row in rows), is_total_row=1)


def get_data(filters=None):
	filters = filters or {}
	Expense = frappe.qb.DocType("Expense")

	query = (
		frappe.qb.from_(Expense)
		.select(
			Expense.name,
			Expense.type,
			Expense.notes,
			Expense.date,
			Expense.amount,
			Expense.paid_on,
			Expense.payment_reference,
			Expense.church,
		)
		.where(Expense.docstatus == 1)
		.orderby(Expense.date, order=Order.desc)
	)

	if filters.get("from_date"):
		query = query.where(Expense.date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(Expense.date < add_days(filters["to_date"], 1))
	if filters.get("type"):
		query = query.where(Expense.type.isin(get_types_within(filters["type"])))
	if filters.get("fund"):
		query = query.where(Expense.associated_fund == filters["fund"])

	return scoped(query, Expense, filters).run(as_dict=True)


def get_types_within(expense_type: str) -> list[str]:
	"""The expense type and, for a group such as Utilities, every type beneath it."""
	if not frappe.db.get_value("Expense Type", expense_type, "is_group"):
		return [expense_type]
	return [expense_type, *get_descendants_of("Expense Type", expense_type, ignore_permissions=True)]
