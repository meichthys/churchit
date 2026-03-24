import frappe

from church.utils import get_church_condition


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Expense", "options": "Expense", "width": 200},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Expense Type", "width": 150},
		{"fieldname": "notes", "fieldtype": "Data", "label": "Notes", "width": 200},
		{"fieldname": "date", "fieldtype": "Date", "label": "Date", "width": 120},
		{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 120},
	]


def get_data(filters=None):
	values = {}
	church_condition = get_church_condition(filters, "church", values)

	return frappe.db.sql(
		f"""
		SELECT name, type, notes, date, amount
		FROM `tabExpense`
		WHERE docstatus < 2
			{church_condition}
		ORDER BY date DESC
		""",
		values,
		as_dict=True,
	)
