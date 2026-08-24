import frappe

from churchit.utils import set_report_link_titles


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
	Fund = frappe.qb.DocType("Fund")
	return frappe.qb.from_(Fund).select(Fund.fund, Fund.balance).run(as_dict=True)
