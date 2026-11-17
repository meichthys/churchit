import frappe
from frappe import _
from frappe.utils import today
from pypika import Order

from churchit.church_ministries.attendance import COUNTED_TYPES
from churchit.church_scope import get_church_columns, scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = filters or {}
	if filters.get("group"):
		frappe.has_permission("Group", doc=filters["group"], throw=True)
	if filters.get("function"):
		frappe.has_permission("Function", doc=filters["function"], throw=True)
	columns = [*get_columns(), *get_church_columns(filters)]
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "start_date", "fieldtype": "Date", "label": _("Date"), "width": 110},
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 200},
		{
			"fieldname": "type",
			"fieldtype": "Link",
			"label": _("Type"),
			"options": "Function Type",
			"width": 180,
		},
		{
			"fieldname": "attendance_type",
			"fieldtype": "Link",
			"label": _("Attendance Type"),
			"options": "Function Attendance Type",
			"width": 150,
		},
		{
			"fieldname": "name",
			"fieldtype": "Link",
			"label": _("Function"),
			"options": "Function",
			"width": 200,
		},
		{"fieldname": "group", "fieldtype": "Link", "label": _("Group"), "options": "Group", "width": 180},
	]


def get_data(filters=None):
	filters = filters or {}
	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")

	query = (
		frappe.qb.from_(Attendance)
		.join(Function)
		.on(Function.name == Attendance.parent)
		.select(
			Function.start_date,
			Attendance.person,
			Function.type,
			Attendance.attendance_type,
			Function.name,
			Function.group,
			Function.church,
		)
		.where(Attendance.person.isnotnull() & Attendance.attendance_type.isin(COUNTED_TYPES))
		.where((Function.start_date <= today()) & (Function.auto_repeat == 0))
		.orderby(Function.start_date, order=Order.desc)
		.orderby(Attendance.person)
	)
	if filters.get("from_date"):
		query = query.where(Function.start_date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(Function.start_date <= filters["to_date"])
	if filters.get("function"):
		query = query.where(Function.name == filters["function"])
	if filters.get("group"):
		query = query.where(Function.group == filters["group"])
	return scoped(query, Function, filters).run(as_dict=True)
