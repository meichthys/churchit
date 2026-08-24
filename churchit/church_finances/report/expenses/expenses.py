import frappe
from pypika import Order

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Expense", "options": "Expense", "width": 200},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Expense Type", "width": 150},
		{"fieldname": "notes", "fieldtype": "Data", "label": "Notes", "width": 200},
		{"fieldname": "date", "fieldtype": "Date", "label": "Date", "width": 120},
		{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 120},
	]


def get_data():
	Expense = frappe.qb.DocType("Expense")

	return (
		frappe.qb.from_(Expense)
		.select(Expense.name, Expense.type, Expense.notes, Expense.date, Expense.amount)
		.where(Expense.docstatus < 2)
		.orderby(Expense.date, order=Order.desc)
		.run(as_dict=True)
	)
