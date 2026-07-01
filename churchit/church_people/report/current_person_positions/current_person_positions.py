import frappe
from frappe.utils import today

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 180},
		{"fieldname": "position", "fieldtype": "Link", "label": "Position", "options": "Position Type", "width": 180},
		{"fieldname": "start_date", "fieldtype": "Date", "label": "Start Date", "width": 120},
		{"fieldname": "end_date", "fieldtype": "Date", "label": "End Date", "width": 120},
		{"fieldname": "notes", "fieldtype": "Small Text", "label": "Notes", "width": 300},
	]


def get_data(filters=None):
	values = {"today": today()}

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
			AND `tabPosition`.position IS NOT NULL
			AND `tabPosition`.start_date <= %(today)s
			AND (`tabPosition`.end_date IS NULL OR `tabPosition`.end_date >= %(today)s)
		ORDER BY `tabPerson`.name, `tabPosition`.start_date
		""",
		values,
		as_dict=True,
	)
