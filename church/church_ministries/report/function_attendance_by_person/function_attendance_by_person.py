import frappe

from church.utils import CHURCH_COLUMN, get_church_condition, show_church_column


def execute(filters=None):
	return get_columns(filters), get_data(filters)


def get_columns(filters=None):
	cols = [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
	]
	if show_church_column(filters):
		cols.append(CHURCH_COLUMN)
	cols += [
		{"fieldname": "function", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 200},
		{"fieldname": "type", "fieldtype": "Link", "label": "Function Type", "options": "Function Type", "width": 150},
		{"fieldname": "start_date", "fieldtype": "Date", "label": "Date", "width": 120},
		{"fieldname": "attendance_type", "fieldtype": "Link", "label": "Attendance Type", "options": "Function Attendance Type", "width": 150},
	]
	return cols


def get_data(filters=None):
	filters = filters or {}
	conditions = ""
	values = {}

	conditions += get_church_condition(filters, "`tabFunction`.church", values)
	church_select = ", `tabFunction`.church" if show_church_column(filters) else ""

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
			`tabFunction Attendance`.person{church_select},
			`tabFunction Attendance`.parent as `function`,
			`tabFunction`.type,
			`tabFunction`.start_date,
			`tabFunction Attendance`.attendance_type
		FROM `tabFunction Attendance`
		INNER JOIN `tabFunction` ON `tabFunction`.name = `tabFunction Attendance`.parent
		WHERE `tabFunction Attendance`.attendance_type IN ('Assumed', 'Confirmed')
			{conditions}
		ORDER BY `tabFunction`.start_date DESC, `tabFunction Attendance`.person
		""",
		values,
		as_dict=True,
	)
