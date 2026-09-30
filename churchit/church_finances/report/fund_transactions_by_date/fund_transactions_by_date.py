import frappe
from frappe import _
from pypika import Order

from churchit.church_scope import scoped
from churchit.query import Date
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "fund", "fieldtype": "Data", "label": _("Fund"), "width": 200},
		{"fieldname": "amount", "fieldtype": "Currency", "label": _("Amount"), "width": 120},
		{"fieldname": "notes", "fieldtype": "Data", "label": _("Notes"), "width": 300},
		{"fieldname": "creation", "fieldtype": "Datetime", "label": _("Date"), "width": 150},
	]


def get_data(filters):
	filters = filters or {}
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	Fund = frappe.qb.DocType("Fund")
	Transaction = frappe.qb.DocType("Financial Transaction")

	query = (
		frappe.qb.from_(Fund)
		.join(Transaction)
		.on(Transaction.parent == Fund.name)
		.select(Fund.fund, Transaction.amount, Transaction.notes, Transaction.creation)
		.where(Transaction.parenttype == "Fund")
		.orderby(Fund.fund)
		.orderby(Transaction.creation, order=Order.desc)
	)

	if from_date:
		query = query.where(Date(Transaction.creation) >= from_date)
	if to_date:
		query = query.where(Date(Transaction.creation) <= to_date)

	return scoped(query, Fund, filters).run(as_dict=True)
