import frappe

from church.utils import get_church_condition


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "status", "fieldtype": "Link", "label": "Status", "options": "Prayer Request Status", "width": 120},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Prayer Request Type", "width": 120},
		{"fieldname": "recipient", "fieldtype": "Dynamic Link", "label": "Recipient", "options": "recipient_type", "width": 150},
		{"fieldname": "request", "fieldtype": "Data", "label": "Request", "width": 300},
	]


def get_data(filters):
	filters = filters or {}
	values = {"request_since": filters.get("request_since")}
	church_condition = get_church_condition(filters, "church", values)

	return frappe.db.sql(
		f"""
		SELECT status, type, recipient_type, recipient, request
		FROM `tabPrayer Request`
		WHERE creation > %(request_since)s
			AND status = 'answered'
			{church_condition}
		""",
		values,
		as_dict=True,
	)
