import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Request", "options": "Prayer Request", "width": 180},
		{"fieldname": "title", "fieldtype": "Data", "label": "Title", "width": 240},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Prayer Request Type", "width": 130},
		{"fieldname": "urgent", "fieldtype": "Check", "label": "Urgent", "width": 70},
		{"fieldname": "requestor", "fieldtype": "Link", "label": "Requestor", "options": "Person", "width": 200},
		{"fieldname": "days_open", "fieldtype": "Int", "label": "Days Open", "width": 100},
		{"fieldname": "status", "fieldtype": "Link", "label": "Status", "options": "Prayer Request Status", "width": 140},
	]


def get_data(filters=None):
	return frappe.db.sql(
		"""
		SELECT
			pr.name, pr.title, pr.type, pr.urgent, pr.requestor, pr.status,
			DATEDIFF(CURDATE(), pr.creation) AS days_open
		FROM `tabPrayer Request` pr
		WHERE COALESCE(pr.status, '') NOT IN ('Answered', 'Archived', 'Closed')
		ORDER BY pr.urgent DESC, pr.creation DESC
		""",
		as_dict=True,
	)
