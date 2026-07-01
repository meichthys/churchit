import frappe

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 240},
		{"fieldname": "first_gift_date", "fieldtype": "Date", "label": "First Gift", "width": 120},
		{"fieldname": "first_gift_amount", "fieldtype": "Currency", "label": "First Gift Amount", "width": 160},
	]


def get_data(filters=None):
	window_days = (filters or {}).get("window_days", 90)
	return frappe.db.sql(
		"""
		SELECT
			d.person,
			MIN(c.date) AS first_gift_date,
			(
				SELECT d2.amount FROM `tabDonation` d2
				JOIN `tabCollection` c2 ON c2.name = d2.parent
				WHERE d2.person = d.person AND c2.docstatus = 1
				ORDER BY c2.date ASC LIMIT 1
			) AS first_gift_amount
		FROM `tabDonation` d
		JOIN `tabCollection` c ON c.name = d.parent
		WHERE d.person IS NOT NULL AND c.docstatus = 1
		GROUP BY d.person
		HAVING first_gift_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
		ORDER BY first_gift_date DESC
		""",
		(window_days,),
		as_dict=True,
	)
