import frappe

from church.utils import CHURCH_COLUMN, get_church_condition, set_report_link_titles, show_church_column


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = [
		{"fieldname": "name", "fieldtype": "Link", "label": "Expense", "options": "Expense", "width": 200},
	]
	if show_church_column(filters):
		cols.append(CHURCH_COLUMN)
	cols += [
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Expense Type", "width": 150},
		{"fieldname": "notes", "fieldtype": "Data", "label": "Notes", "width": 200},
		{"fieldname": "date", "fieldtype": "Date", "label": "Date", "width": 120},
		{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 120},
	]
	return cols


def get_data(filters=None):
	values = {}
	church_condition = get_church_condition(filters, "church", values)
	church_select = ", church" if show_church_column(filters) else ""

	return frappe.db.sql(
		f"""
		SELECT name{church_select}, type, notes, date, amount
		FROM `tabExpense`
		WHERE docstatus < 2
			{church_condition}
		ORDER BY date DESC
		""",
		values,
		as_dict=True,
	)
