import frappe

from church.utils import get_church_condition, set_report_link_titles


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = [
		{"fieldname": "status", "fieldtype": "Link", "label": "Status", "options": "Prayer Request Status", "width": 120},
	]
	cols += [
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Prayer Request Type", "width": 120},
		{"fieldname": "recipient", "fieldtype": "Dynamic Link", "label": "Recipient", "options": "recipient_type", "width": 150},
		{"fieldname": "request", "fieldtype": "Data", "label": "Request", "width": 300},
		{"fieldname": "name", "fieldtype": "Link", "label": "Link to Request", "options": "Prayer Request", "width": 150},
	]
	return cols


def get_data(filters):
	filters = filters or {}
	values = {"request_since": filters.get("request_since")}
	church_condition = get_church_condition(filters, "Prayer Request", "`tabPrayer Request`.`name`", values)

	return frappe.db.sql(
		f"""
		SELECT status, type, recipient_type, recipient, request, name
		FROM `tabPrayer Request`
		WHERE creation > %(request_since)s
			{church_condition}
		""",
		values,
		as_dict=True,
	)
