import frappe

from church.utils import get_church_condition, set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "church", "fieldtype": "Link", "label": "Church", "options": "Church", "width": 200},
		{"fieldname": "fund", "fieldtype": "Data", "label": "Fund", "width": 200},
		{"fieldname": "balance", "fieldtype": "Currency", "label": "Balance", "width": 150},
	]


def get_data(filters=None):
	values = {}
	church_condition = get_church_condition(filters, "church", values)

	return frappe.db.sql(
		f"""
		SELECT church, fund, balance
		FROM `tabFund`
		WHERE 1=1
			{church_condition}
		""",
		values,
		as_dict=True,
	)
