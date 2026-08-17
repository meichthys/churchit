import frappe

from churchit.contacts import primary_email_sql, primary_phone_sql
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 220},
		{"fieldname": "creation", "fieldtype": "Date", "label": "First Seen", "width": 120},
		{"fieldname": "first_visit", "fieldtype": "Link", "label": "First Function", "options": "Function", "width": 200},
		{"fieldname": "first_visit_date", "fieldtype": "Date", "label": "First Visit", "width": 110},
		{"fieldname": "visit_count", "fieldtype": "Int", "label": "Visits", "width": 80},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data(filters=None):
	days = (filters or {}).get("days", 60)
	return frappe.db.sql(
		f"""
		SELECT
			p.name,
			p.creation,
			{primary_phone_sql("p")} AS primary_phone,
			{primary_email_sql("p")} AS email,
			(
				SELECT fa2.parent
				FROM `tabFunction Attendance` fa2
				JOIN `tabFunction` f2 ON f2.name = fa2.parent
				WHERE fa2.person = p.name
				ORDER BY f2.start_date ASC LIMIT 1
			) AS first_visit,
			(
				SELECT MIN(f2.start_date)
				FROM `tabFunction Attendance` fa2
				JOIN `tabFunction` f2 ON f2.name = fa2.parent
				WHERE fa2.person = p.name
			) AS first_visit_date,
			(
				SELECT COUNT(*)
				FROM `tabFunction Attendance` fa3
				WHERE fa3.person = p.name
			) AS visit_count
		FROM `tabPerson` p
		WHERE p.membership_status IS NULL
			AND p.creation >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
		ORDER BY p.creation DESC
		""",
		(days,),
		as_dict=True,
	)
