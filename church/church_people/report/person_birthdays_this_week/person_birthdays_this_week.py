import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
		{"fieldname": "birthday", "fieldtype": "Date", "label": "Birthday", "width": 120},
	]


def get_data():
	return frappe.db.sql(
		"""
		SELECT p.name, le.date AS birthday
		FROM `tabPerson` p
		JOIN `tabLife Event` le
			ON le.parent = p.name
			AND le.parenttype = 'Person'
			AND le.event_type = 'Birth'
		WHERE le.date IS NOT NULL
			AND WEEK(le.date, 1) = WEEK(CURDATE(), 1)
			AND MONTH(le.date) = MONTH(CURDATE())
		ORDER BY DAYOFWEEK(le.date), p.full_name
		""",
		as_dict=True,
	)
