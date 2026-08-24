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
	]


def get_data(filters):
	request_since = (filters or {}).get("request_since")

	Prayer = frappe.qb.DocType("Prayer Request")

	return (
		frappe.qb.from_(Prayer)
		.select(Prayer.status, Prayer.type, Prayer.recipient_type, Prayer.recipient, Prayer.details)
		.where((Prayer.creation > request_since) & (Prayer.status == "answered"))
		.run(as_dict=True)
	)
