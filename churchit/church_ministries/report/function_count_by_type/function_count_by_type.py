import frappe
from frappe.query_builder.functions import Count

from churchit.query import Date
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "type", "fieldtype": "Data", "label": "Type", "width": 200},
		{"fieldname": "counts", "fieldtype": "Int", "label": "Count", "width": 100},
	]


def get_data(filters):
	filters = filters or {}
	start = filters.get("start")
	end = filters.get("end")

	Function = frappe.qb.DocType("Function")

	return (
		frappe.qb.from_(Function)
		.select(Function.type.as_("type"), Count(Function.name).as_("counts"))
		.where(
			Function.start_date.isnull() | Function.end_date.isnull() | Date(Function.start_date)[start:end]
		)
		.groupby(Function.type)
		.run(as_dict=True)
	)
