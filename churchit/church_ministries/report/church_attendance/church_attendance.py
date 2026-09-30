import frappe
from frappe import _
from pypika import Order

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles

COUNTED_TYPES = ("Confirmed", "Assumed", "Checked-In")


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 200},
		{"fieldname": "function_name", "fieldtype": "Data", "label": _("Function"), "width": 200},
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
	]


def get_data(filters=None):
	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")
	AttendanceType = frappe.qb.DocType("Function Attendance Type")

	counted = (
		frappe.qb.from_(AttendanceType)
		.select(AttendanceType.name)
		.where(AttendanceType.type.isin(list(COUNTED_TYPES)))
	)

	query = (
		frappe.qb.from_(Attendance)
		.join(Function)
		.on(Function.name == Attendance.parent)
		.select(
			Attendance.person,
			Function.function_name,
			Function.type,
			Attendance.attendance_type,
			Function.name,
		)
		.where(Attendance.person.isnotnull() & Attendance.attendance_type.isin(counted))
		.orderby(Function.modified, order=Order.desc)
	)
	return scoped(query, Function, filters).run(as_dict=True)
