import frappe

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
		{"fieldname": "position", "fieldtype": "Link", "label": "Position", "options": "Position Type", "width": 180},
		{"fieldname": "start_date", "fieldtype": "Date", "label": "Start Date", "width": 120},
		{"fieldname": "end_date", "fieldtype": "Date", "label": "End Date", "width": 120},
		{"fieldname": "notes", "fieldtype": "Small Text", "label": "Notes", "width": 300},
	]


def get_data():
	return frappe.db.sql(
		"""
		SELECT
			`tabPerson`.name,
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
		ORDER BY `tabPosition`.end_date, `tabPerson`.name
		""",
		as_dict=True,
	)
