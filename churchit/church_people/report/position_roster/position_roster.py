import frappe

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "position", "fieldtype": "Link", "label": "Position", "options": "Position Type", "width": 160},
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 220},
		{"fieldname": "start_date", "fieldtype": "Date", "label": "Term Start", "width": 110},
		{"fieldname": "end_date", "fieldtype": "Date", "label": "Term End", "width": 110},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data(filters=None):
	only_active = (filters or {}).get("only_active", 1)
	return frappe.db.sql(
		"""
		SELECT
			pos.position,
			pos.parent AS person,
			pos.start_date,
			pos.end_date,
			p.primary_phone,
			p.email
		FROM `tabPosition` pos
		LEFT JOIN `tabPerson` p ON p.name = pos.parent
		WHERE pos.parenttype = 'Person'
			AND (%(only_active)s = 0 OR pos.end_date IS NULL OR pos.end_date >= CURDATE())
		ORDER BY pos.position, p.full_name
		""",
		{"only_active": 1 if only_active else 0},
		as_dict=True,
	)
