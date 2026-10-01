import frappe
from frappe import _
from pypika import Order

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "name",
			"fieldtype": "Link",
			"label": _("Function"),
			"options": "Function",
			"width": 300,
		},
		{"fieldname": "function_name", "fieldtype": "Data", "label": _("Name"), "width": 200},
		{
			"fieldname": "type",
			"fieldtype": "Link",
			"label": _("Type"),
			"options": "Function Type",
			"width": 200,
		},
	]


def get_data(filters=None):
	Function = frappe.qb.DocType("Function")

	query = (
		frappe.qb.from_(Function)
		.select(Function.name, Function.function_name, Function.type)
		.orderby(Function.modified, order=Order.desc)
	)
	return scoped(query, Function, filters).run(as_dict=True)
