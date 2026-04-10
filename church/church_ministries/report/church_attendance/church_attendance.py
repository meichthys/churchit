import frappe

from church.utils import get_church_condition, set_report_link_titles


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
	]
	cols += [
		{"fieldname": "function_name", "fieldtype": "Data", "label": "Function", "width": 200},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Function Type", "width": 180},
		{"fieldname": "attendance_type", "fieldtype": "Link", "label": "Attendance Type", "options": "Function Attendance Type", "width": 150},
		{"fieldname": "name", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 200},
	]
	return cols


def get_data(filters=None):
	values = {}
	church_condition = get_church_condition(filters, "Function", "`tabFunction`.`name`", values)

	return frappe.db.sql(
		f"""
		SELECT
			`tabFunction Attendance`.person,
			`tabFunction`.function_name,
			`tabFunction`.type,
			`tabFunction Attendance`.attendance_type,
			`tabFunction`.name
		FROM `tabFunction Attendance`
		INNER JOIN `tabFunction` ON `tabFunction`.name = `tabFunction Attendance`.parent
		WHERE `tabFunction Attendance`.person IS NOT NULL
			AND `tabFunction Attendance`.attendance_type IN (
				SELECT name FROM `tabFunction Attendance Type` WHERE type IN ('Confirmed', 'Assumed')
			)
			{church_condition}
		ORDER BY `tabFunction`.modified DESC
		""",
		values,
		as_dict=True,
	)
