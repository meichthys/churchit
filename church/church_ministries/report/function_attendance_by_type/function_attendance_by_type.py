import frappe

from church.utils import get_church_condition, set_report_link_titles


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = [
		{"fieldname": "function", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 200},
	]
	cols.append({"fieldname": "attendance_count", "fieldtype": "Int", "label": "Attendance Count", "width": 150})
	return cols


def get_data(filters=None):
	conditions = ""
	values = {}

	conditions += get_church_condition(filters, "Function", "`tabFunction`.`name`", values)

	return frappe.db.sql(
		f"""
		SELECT
			`tabFunction Attendance`.parent as `function`,
			count(`tabFunction Attendance`.person) as attendance_count
		FROM `tabFunction Attendance`
		INNER JOIN `tabFunction` ON `tabFunction`.name = `tabFunction Attendance`.parent
		WHERE `tabFunction Attendance`.attendance_type IN (
				SELECT name FROM `tabFunction Attendance Type` WHERE type IN ('Assumed', 'Confirmed')
			)
			{conditions}
		GROUP BY `tabFunction Attendance`.parent
		""",
		values,
		as_dict=True,
	)
