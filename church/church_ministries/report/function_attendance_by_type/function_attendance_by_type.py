import frappe

from church.utils import set_report_link_titles


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
	return frappe.db.sql(
		"""
		SELECT
			`tabFunction Attendance`.parent as `function`,
			count(`tabFunction Attendance`.person) as attendance_count
		FROM `tabFunction Attendance`
		INNER JOIN `tabFunction` ON `tabFunction`.name = `tabFunction Attendance`.parent
		WHERE `tabFunction Attendance`.attendance_type IN (
				SELECT name FROM `tabFunction Attendance Type` WHERE type IN ('Assumed', 'Confirmed')
			)
		GROUP BY `tabFunction Attendance`.parent
		""",
		as_dict=True,
	)
