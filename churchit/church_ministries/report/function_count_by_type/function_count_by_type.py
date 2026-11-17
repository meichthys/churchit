import frappe
from frappe import _
from frappe.query_builder.functions import Count

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "type", "fieldtype": "Data", "label": _("Type"), "width": 200},
		{"fieldname": "counts", "fieldtype": "Int", "label": _("Count"), "width": 100},
	]


def get_data(filters):
	"""Functions per type that start between the Start and End Dates, each given date applied, templates left out."""
	filters = filters or {}

	Function = frappe.qb.DocType("Function")

	query = (
		frappe.qb.from_(Function)
		.select(Function.type.as_("type"), Count(Function.name).as_("counts"))
		.where(Function.auto_repeat == 0)
		.groupby(Function.type)
	)
	if filters.get("start"):
		query = query.where(Function.start_date >= filters["start"])
	if filters.get("end"):
		query = query.where(Function.start_date <= filters["end"])
	return scoped(query, Function, filters).run(as_dict=True)
