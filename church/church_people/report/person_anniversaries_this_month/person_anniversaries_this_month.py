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
		{"fieldname": "anniversary", "fieldtype": "Date", "label": "Anniversary", "width": 120},
		{"fieldname": "marriage_years", "fieldtype": "Int", "label": "Years", "width": 80},
		{"fieldname": "spouse", "fieldtype": "Link", "label": "Spouse", "options": "Person", "width": 200},
	]


def get_data():
	return frappe.db.sql(
		"""
		SELECT name, anniversary, marriage_years, spouse
		FROM `tabPerson`
		WHERE anniversary IS NOT NULL
			AND MONTH(anniversary) = MONTH(CURDATE())
			AND is_head_of_household = 1
		ORDER BY DAYOFMONTH(anniversary), full_name
		""",
		as_dict=True,
	)
