import frappe

from churchit.contacts import primary_email_sql, primary_phone_sql
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
		{"fieldname": "birthday", "fieldtype": "Date", "label": "Birthday", "width": 120},
		{"fieldname": "age", "fieldtype": "Int", "label": "Turning", "width": 80},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data():
	return frappe.db.sql(
		f"""
		SELECT
			p.name,
			le.date AS birthday,
			YEAR(CURDATE()) - YEAR(le.date) AS age,
			{primary_phone_sql("p")} AS primary_phone,
			{primary_email_sql("p")} AS email
		FROM `tabPerson` p
		JOIN `tabLife Event` le
			ON le.parent = p.name
			AND le.parenttype = 'Person'
			AND le.event_type = 'Birth'
		WHERE le.date IS NOT NULL
			AND MONTH(le.date) = MONTH(CURDATE())
		ORDER BY DAYOFMONTH(le.date), p.full_name
		""",
		as_dict=True,
	)
