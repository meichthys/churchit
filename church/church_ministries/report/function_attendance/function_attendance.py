import frappe


def execute(filters=None):
	return get_columns(), get_data()


def get_columns():
	return [
		{"fieldname": "function", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 200},
		{"fieldname": "attendance_count", "fieldtype": "Int", "label": "Attendance Count", "width": 150},
	]


def get_data():
	church_condition = ""
	values = {}

	if "System Manager" not in frappe.get_roles():
		church_condition = """AND `tabFunction`.church IN (
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
			{church_condition}
		GROUP BY `tabFunction Attendance`.parent
		""",
		values,
		as_dict=True,
	)
