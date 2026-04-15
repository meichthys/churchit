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
		SELECT name, birthday
		FROM `tabPerson`
		WHERE birthday IS NOT NULL
			AND WEEK(birthday, 1) = WEEK(CURDATE(), 1)
			AND MONTH(birthday) = MONTH(CURDATE())
		ORDER BY DAYOFWEEK(birthday), full_name
		""",
		as_dict=True,
	)
