import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 240},
		{"fieldname": "gift_count", "fieldtype": "Int", "label": "# Gifts", "width": 80},
		{"fieldname": "ytd_amount", "fieldtype": "Currency", "label": "YTD Amount", "width": 140},
		{"fieldname": "avg_gift", "fieldtype": "Currency", "label": "Avg Gift", "width": 120},
		{"fieldname": "last_gift_date", "fieldtype": "Date", "label": "Last Gift", "width": 110},
		{"fieldname": "prior_year_amount", "fieldtype": "Currency", "label": "Prior Year", "width": 140},
	]


def get_data(filters=None):
	year = (filters or {}).get("year") or frappe.utils.now_datetime().year
	return frappe.db.sql(
		"""
		SELECT
			d.person,
			COUNT(*) AS gift_count,
			SUM(d.amount) AS ytd_amount,
			AVG(d.amount) AS avg_gift,
			MAX(c.date) AS last_gift_date,
			(
				SELECT SUM(d2.amount)
				FROM `tabDonation` d2
				JOIN `tabCollection` c2 ON c2.name = d2.parent
				WHERE d2.person = d.person
					AND YEAR(c2.date) = %(year)s - 1
					AND c2.docstatus = 1
			) AS prior_year_amount
		FROM `tabDonation` d
		JOIN `tabCollection` c ON c.name = d.parent
		WHERE d.person IS NOT NULL
			AND YEAR(c.date) = %(year)s
			AND c.docstatus = 1
		GROUP BY d.person
		ORDER BY ytd_amount DESC
		""",
		{"year": year},
		as_dict=True,
	)
