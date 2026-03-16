import frappe
from frappe.utils import today


def execute(filters=None):
	return get_columns(), get_data()


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 180},
		{"fieldname": "position", "fieldtype": "Link", "label": "Position", "options": "Position Type", "width": 180},
		{"fieldname": "start_date", "fieldtype": "Date", "label": "Start Date", "width": 120},
		{"fieldname": "end_date", "fieldtype": "Date", "label": "End Date", "width": 120},
		{"fieldname": "notes", "fieldtype": "Small Text", "label": "Notes", "width": 300},
	]


def get_data():
	church_condition = ""
	values = {"today": today()}

	if "System Manager" not in frappe.get_roles():
		church_condition = """AND `tabPerson`.church IN (
			SELECT for_value FROM `tabUser Permission`
			WHERE user = %(user)s AND allow = 'Church'
		)"""
		values["user"] = frappe.session.user

	return frappe.db.sql(
		f"""
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
			{church_condition}
		ORDER BY `tabPerson`.name, `tabPosition`.start_date
		""",
		values,
		as_dict=True,
	)
