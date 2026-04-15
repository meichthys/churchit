import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "fund", "fieldtype": "Data", "label": "Fund", "width": 200},
		{"fieldname": "balance", "fieldtype": "Currency", "label": "Balance", "width": 150},
	]


def get_data():
	return frappe.db.sql(
		"""
		SELECT fund, balance
		FROM `tabFund`
		""",
		as_dict=True,
	)
