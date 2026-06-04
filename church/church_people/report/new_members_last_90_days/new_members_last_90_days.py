import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 220},
		{"fieldname": "membership_date", "fieldtype": "Date", "label": "Joined", "width": 110},
		{"fieldname": "membership_status", "fieldtype": "Link", "label": "Status", "options": "Member Status", "width": 110},
		{"fieldname": "family", "fieldtype": "Link", "label": "Family", "options": "Family", "width": 200},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data(filters=None):
	days = (filters or {}).get("days", 90)
	return frappe.db.sql(
		"""
		SELECT
			p.name,
			p.membership_status,
			p.family,
			p.primary_phone,
			p.email,
			(
				SELECT le.date
				FROM `tabLife Event` le
				WHERE le.parent = p.name
					AND le.event_type = 'Membership'
				ORDER BY le.date ASC
				LIMIT 1
			) AS membership_date
		FROM `tabPerson` p
		WHERE p.membership_status = 'Active'
		HAVING membership_date IS NOT NULL
			AND membership_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
		ORDER BY membership_date DESC
		""",
		(days,),
		as_dict=True,
	)
