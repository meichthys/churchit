import frappe
from pypika import Order

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
		{"fieldname": "function", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 200},
		{"fieldname": "type", "fieldtype": "Link", "label": "Function Type", "options": "Function Type", "width": 150},
		{"fieldname": "start_date", "fieldtype": "Date", "label": "Date", "width": 120},
		{"fieldname": "attendance_type", "fieldtype": "Link", "label": "Attendance Type", "options": "Function Attendance Type", "width": 150},
	]


def get_data(filters=None):
	filters = filters or {}

	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")
	AttendanceType = frappe.qb.DocType("Function Attendance Type")

	counted_types = (
		frappe.qb.from_(AttendanceType)
		.select(AttendanceType.name)
		.where(AttendanceType.type.isin(["Assumed", "Confirmed"]))
	)

	query = (
		frappe.qb.from_(Attendance)
		.inner_join(Function)
		.on(Function.name == Attendance.parent)
		.select(
			Attendance.person,
			Attendance.parent.as_("function"),
			Function.type,
			Function.start_date,
			Attendance.attendance_type,
		)
		.where(Attendance.attendance_type.isin(counted_types))
		.orderby(Function.start_date, order=Order.desc)
		.orderby(Attendance.person)
	)

	if filters.get("person"):
		query = query.where(Attendance.person == filters["person"])
	if filters.get("function_type"):
		query = query.where(Function.type == filters["function_type"])
	if filters.get("start"):
		query = query.where(Function.start_date >= filters["start"])
	if filters.get("end"):
		query = query.where(Function.start_date <= filters["end"])

	return query.run(as_dict=True)
