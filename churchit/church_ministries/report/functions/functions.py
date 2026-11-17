import frappe
from frappe import _
from pypika import Order

from churchit.church_scope import get_church_columns, scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = [*get_columns(), *get_church_columns(filters)]
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
		{"fieldname": "start_date", "fieldtype": "Date", "label": _("Start Date"), "width": 110},
		{
			"fieldname": "associated_ministry",
			"fieldtype": "Link",
			"label": _("Ministry"),
			"options": "Ministry",
			"align": "left",
			"width": 180,
		},
		{
			"fieldname": "type",
			"fieldtype": "Link",
			"label": _("Type"),
			"options": "Function Type",
			"width": 200,
		},
		{"fieldname": "attendance_total", "fieldtype": "Int", "label": _("Attendance"), "width": 110},
	]


def get_data(filters=None):
	filters = filters or {}
	Function = frappe.qb.DocType("Function")

	query = (
		frappe.qb.from_(Function)
		.select(
			Function.name,
			Function.start_date,
			Function.associated_ministry,
			Function.type,
			Function.attendance_total,
			Function.church,
		)
		.where(Function.auto_repeat == 0)
		.orderby(Function.start_date, order=Order.desc)
	)
	if filters.get("from_date"):
		query = query.where(Function.start_date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(Function.start_date <= filters["to_date"])

	return scoped(query, Function, filters).run(as_dict=True)
