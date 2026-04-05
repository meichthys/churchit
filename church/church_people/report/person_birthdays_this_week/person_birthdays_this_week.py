import frappe

from church.utils import CHURCH_COLUMN, get_church_condition, set_report_link_titles, show_church_column


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
	]
	if show_church_column(filters):
		cols.append(CHURCH_COLUMN)
	cols.append({"fieldname": "birthday", "fieldtype": "Date", "label": "Birthday", "width": 120})
	return cols


def get_data(filters=None):
	values = {}
	church_condition = get_church_condition(filters, "church", values)
	church_select = ", church" if show_church_column(filters) else ""

	return frappe.db.sql(
		f"""
		SELECT name{church_select}, birthday
		FROM `tabPerson`
		WHERE birthday IS NOT NULL
			AND WEEK(birthday, 1) = WEEK(CURDATE(), 1)
			AND MONTH(birthday) = MONTH(CURDATE())
			{church_condition}
		ORDER BY DAYOFWEEK(birthday), full_name
		""",
		values,
		as_dict=True,
	)
