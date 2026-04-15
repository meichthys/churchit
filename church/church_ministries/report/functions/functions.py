import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 300},
		{"fieldname": "function_name", "fieldtype": "Data", "label": "Name", "width": 200},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Function Type", "width": 200},
	]


def get_data():
	return frappe.db.sql(
		"""
		SELECT name, function_name, type
		FROM `tabFunction`
		ORDER BY modified DESC
		""",
		as_dict=True,
	)
