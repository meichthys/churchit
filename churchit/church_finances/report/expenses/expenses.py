import frappe
from frappe import _
from pypika import Order

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
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
	]


def get_data(filters=None):
	Expense = frappe.qb.DocType("Expense")

	query = (
		frappe.qb.from_(Expense)
		.select(Expense.name, Expense.type, Expense.notes, Expense.date, Expense.amount)
		.where(Expense.docstatus < 2)
		.orderby(Expense.date, order=Order.desc)
	)
	return scoped(query, Expense, filters).run(as_dict=True)
