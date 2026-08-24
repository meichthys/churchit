import frappe
from frappe.query_builder.functions import Count

from churchit.utils import set_report_link_titles

COUNTED_TYPES = ("Assumed", "Confirmed")


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "function", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 200},
		{"fieldname": "attendance_count", "fieldtype": "Int", "label": "Attendance Count", "width": 150},
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
			Attendance.parent.as_("function"),
			Count(Attendance.person).as_("attendance_count"),
		)
		.where(Attendance.attendance_type.isin(counted))
		.groupby(Attendance.parent)
		.run(as_dict=True)
	)
