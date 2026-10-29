import frappe
from frappe import _
from frappe.utils import today
from pypika import Order

from churchit.church_ministries.attendance import COUNTED_TYPES
from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = filters or {}
	if filters.get("group"):
		frappe.has_permission("Group", doc=filters["group"], throw=True)
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 200},
		{
			"fieldname": "function",
			"fieldtype": "Link",
			"label": _("Function"),
			"options": "Function",
			"width": 200,
		},
		{
			"fieldname": "type",
			"fieldtype": "Link",
			"label": _("Function Type"),
			"options": "Function Type",
			"width": 150,
		},
		{"fieldname": "group", "fieldtype": "Link", "label": _("Group"), "options": "Group", "width": 180},
		{"fieldname": "start_date", "fieldtype": "Date", "label": _("Date"), "width": 120},
		{
			"fieldname": "attendance_type",
			"fieldtype": "Link",
			"label": _("Attendance Type"),
			"options": "Function Attendance Type",
			"width": 150,
		},
	]


def get_data(filters=None):
	filters = filters or {}

	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")

	query = (
		frappe.qb.from_(Attendance)
		.inner_join(Function)
		.on(Function.name == Attendance.parent)
		.select(
			Attendance.person,
			Attendance.parent.as_("function"),
			Function.type,
			Function.group,
			Function.start_date,
			Attendance.attendance_type,
		)
		.where(Attendance.attendance_type.isin(COUNTED_TYPES) & (Function.start_date <= today()))
		.orderby(Function.start_date, order=Order.desc)
		.orderby(Attendance.person)
	)

	if filters.get("person"):
		query = query.where(Attendance.person == filters["person"])
	if filters.get("function_type"):
		query = query.where(Function.type == filters["function_type"])
	if filters.get("group"):
		query = query.where(Function.group == filters["group"])
	if filters.get("start"):
		query = query.where(Function.start_date >= filters["start"])
	if filters.get("end"):
		query = query.where(Function.start_date <= filters["end"])

	return scoped(query, Function, filters).run(as_dict=True)
