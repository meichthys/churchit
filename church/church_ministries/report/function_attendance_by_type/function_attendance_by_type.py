import frappe


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "function", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 200},
		{"fieldname": "attendance_count", "fieldtype": "Int", "label": "Attendance Count", "width": 150},
	]


def get_data(filters=None):
	conditions = ""
	values = {}

	if filters and filters.get("church"):
		conditions += "AND `tabFunction`.church = %(church)s"
		values["church"] = filters["church"]
	elif "System Manager" not in frappe.get_roles():
		conditions += """AND `tabFunction`.church IN (
			SELECT for_value FROM `tabUser Permission`
			WHERE user = %(user)s AND allow = 'Church'
		)"""
		values["user"] = frappe.session.user

	return frappe.db.sql(
		f"""
		SELECT
			`tabFunction Attendance`.parent as `function`,
			count(`tabFunction Attendance`.person) as attendance_count
		FROM `tabFunction Attendance`
		INNER JOIN `tabFunction` ON `tabFunction`.name = `tabFunction Attendance`.parent
		WHERE `tabFunction Attendance`.attendance_type IN ('Assumed', 'Confirmed')
			{conditions}
		GROUP BY `tabFunction Attendance`.parent
		""",
		values,
		as_dict=True,
	)
