import frappe
from pypika import Order

from churchit.utils import set_report_link_titles

COUNTED_TYPES = ("Confirmed", "Assumed")


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
		{"fieldname": "function_name", "fieldtype": "Data", "label": "Function", "width": 200},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Function Type", "width": 180},
		{"fieldname": "attendance_type", "fieldtype": "Link", "label": "Attendance Type", "options": "Function Attendance Type", "width": 150},
		{"fieldname": "name", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 200},
	]


def get_data():
	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")
	AttendanceType = frappe.qb.DocType("Function Attendance Type")

	counted = (
		frappe.qb.from_(AttendanceType)
		.select(AttendanceType.name)
		.where(AttendanceType.type.isin(list(COUNTED_TYPES)))
	)

	return (
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
		.run(as_dict=True)
	)
