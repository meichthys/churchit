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
		{"fieldname": "name", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 300},
		{"fieldname": "function_name", "fieldtype": "Data", "label": "Name", "width": 200},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Function Type", "width": 200},
	]


def get_data():
	Function = frappe.qb.DocType("Function")

	return (
		frappe.qb.from_(Function)
		.select(Function.name, Function.function_name, Function.type)
		.orderby(Function.modified, order=Order.desc)
		.run(as_dict=True)
	)
