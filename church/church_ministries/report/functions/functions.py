import frappe

from church.utils import CHURCH_COLUMN, get_church_condition, show_church_column


def execute(filters=None):
	return get_columns(filters), get_data(filters)


def get_columns(filters=None):
	cols = [
		{"fieldname": "name", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 300},
		{"fieldname": "function_name", "fieldtype": "Data", "label": "Name", "width": 200},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Function Type", "width": 200},
	]
	if show_church_column(filters):
		cols.append(CHURCH_COLUMN)
	return cols


def get_data(filters=None):
	values = {}
	church_condition = get_church_condition(filters, "church", values)
	church_select = ", church" if show_church_column(filters) else ""

	return frappe.db.sql(
		f"""
		SELECT name, function_name, type{church_select}
		FROM `tabFunction`
		WHERE 1=1
			{church_condition}
		ORDER BY modified DESC
		""",
		values,
		as_dict=True,
	)
