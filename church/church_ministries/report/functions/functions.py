import frappe

from church.utils import get_church_condition, set_report_link_titles


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = [
		{"fieldname": "name", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 300},
		{"fieldname": "function_name", "fieldtype": "Data", "label": "Name", "width": 200},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Function Type", "width": 200},
	]
	return cols


def get_data(filters=None):
	values = {}
	church_condition = get_church_condition(filters, "Function", "`tabFunction`.`name`", values)

	return frappe.db.sql(
		f"""
		SELECT name, function_name, type
		FROM `tabFunction`
		WHERE 1=1
			{church_condition}
		ORDER BY modified DESC
		""",
		values,
		as_dict=True,
	)
