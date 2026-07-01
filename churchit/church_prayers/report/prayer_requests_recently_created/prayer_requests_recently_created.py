import frappe

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "status", "fieldtype": "Link", "label": "Status", "options": "Prayer Request Status", "width": 120},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Prayer Request Type", "width": 120},
		{"fieldname": "recipient", "fieldtype": "Dynamic Link", "label": "Recipient", "options": "recipient_type", "width": 150},
		{"fieldname": "details", "fieldtype": "Data", "label": "Details", "width": 300},
		{"fieldname": "name", "fieldtype": "Link", "label": "Link to Request", "options": "Prayer Request", "width": 150},
	]


def get_data(filters):
	filters = filters or {}
	values = {"request_since": filters.get("request_since")}

	return frappe.db.sql(
		"""
		SELECT status, type, recipient_type, recipient, details, name
		FROM `tabPrayer Request`
		WHERE creation > %(request_since)s
		""",
		values,
		as_dict=True,
	)
