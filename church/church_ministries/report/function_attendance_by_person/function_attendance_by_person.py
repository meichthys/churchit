import frappe

from church.utils import set_report_link_titles


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
	conditions = ""
	values = {}

	if filters.get("person"):
		conditions += " AND `tabFunction Attendance`.person = %(person)s"
		values["person"] = filters["person"]

	if filters.get("function_type"):
		conditions += " AND `tabFunction`.type = %(function_type)s"
		values["function_type"] = filters["function_type"]

	if filters.get("start"):
		conditions += " AND `tabFunction`.start_date >= %(start)s"
		values["start"] = filters["start"]

	if filters.get("end"):
		conditions += " AND `tabFunction`.start_date <= %(end)s"
		values["end"] = filters["end"]

	return frappe.db.sql(
		f"""
		SELECT
			`tabFunction Attendance`.person,
			`tabFunction Attendance`.parent as `function`,
			`tabFunction`.type,
			`tabFunction`.start_date,
			`tabFunction Attendance`.attendance_type
		FROM `tabFunction Attendance`
		INNER JOIN `tabFunction` ON `tabFunction`.name = `tabFunction Attendance`.parent
		WHERE `tabFunction Attendance`.attendance_type IN (
				SELECT name FROM `tabFunction Attendance Type` WHERE type IN ('Assumed', 'Confirmed')
			)
			{conditions}
		ORDER BY `tabFunction`.start_date DESC, `tabFunction Attendance`.person
		""",
		values,
		as_dict=True,
	)
