import frappe


@frappe.whitelist()
def count_weekly_attendance():
	last_week = frappe.utils.add_days(frappe.utils.nowdate(), -7)
	count = frappe.db.sql(
		"""
		SELECT COUNT(fa.name)
		FROM `tabFunction Attendance` fa
		INNER JOIN `tabFunction` f ON fa.parent = f.name
		WHERE f.start_date >= %s
		""",
		(last_week,),
	)[0][0]
	return {
		"value": count or 0,
		"fieldtype": "Int",
		"route": ["List", "Function"],
		"route_options": {"start_date": [">=", last_week]},
	}


