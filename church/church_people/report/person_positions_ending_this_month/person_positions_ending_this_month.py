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
	cols += [
		{"fieldname": "position", "fieldtype": "Link", "label": "Position", "options": "Position Type", "width": 180},
		{"fieldname": "start_date", "fieldtype": "Date", "label": "Start Date", "width": 120},
		{"fieldname": "end_date", "fieldtype": "Date", "label": "End Date", "width": 120},
		{"fieldname": "notes", "fieldtype": "Small Text", "label": "Notes", "width": 300},
	]
	return cols


def get_data(filters=None):
	values = {}
	church_condition = get_church_condition(filters, "`tabPerson`.church", values)
	church_select = ", `tabPerson`.church" if show_church_column(filters) else ""

	return frappe.db.sql(
		f"""
		SELECT
			`tabPerson`.name{church_select},
			`tabPosition`.position,
			`tabPosition`.start_date,
			`tabPosition`.end_date,
			`tabPosition`.notes
		FROM `tabPosition`
		INNER JOIN `tabPerson` ON `tabPerson`.name = `tabPosition`.parent
		WHERE `tabPosition`.parenttype = 'Person'
			AND `tabPosition`.end_date IS NOT NULL
			AND MONTH(`tabPosition`.end_date) = MONTH(CURDATE())
			AND YEAR(`tabPosition`.end_date) = YEAR(CURDATE())
			{church_condition}
		ORDER BY `tabPosition`.end_date, `tabPerson`.name
		""",
		values,
		as_dict=True,
	)
