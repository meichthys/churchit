import frappe
from frappe.query_builder.functions import Count


@frappe.whitelist()
def count_weekly_attendance():
	last_week = frappe.utils.add_days(frappe.utils.nowdate(), -7)

	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")

	count = (
		frappe.qb.from_(Attendance)
		.join(Function)
		.on(Attendance.parent == Function.name)
		.select(Count(Attendance.name))
		.where(Function.start_date >= last_week)
		.run()[0][0]
	)

	return {
		"value": count or 0,
		"fieldtype": "Int",
		"route": ["List", "Function"],
		"route_options": {"start_date": [">=", last_week]},
	}
