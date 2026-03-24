import frappe

from church.utils import CHURCH_COLUMN, get_church_condition, show_church_column


def execute(filters=None):
	return get_columns(filters), get_data(filters)


def get_columns(filters=None):
	cols = [
		{"fieldname": "status", "fieldtype": "Link", "label": "Status", "options": "Prayer Request Status", "width": 120},
	]
	if show_church_column(filters):
		cols.append(CHURCH_COLUMN)
	cols += [
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Prayer Request Type", "width": 120},
		{"fieldname": "recipient", "fieldtype": "Dynamic Link", "label": "Recipient", "options": "recipient_type", "width": 150},
		{"fieldname": "request", "fieldtype": "Data", "label": "Request", "width": 300},
	]
	return cols


def get_data(filters):
	filters = filters or {}
	values = {"request_since": filters.get("request_since")}
	church_condition = get_church_condition(filters, "church", values)
	church_select = ", church" if show_church_column(filters) else ""

	return frappe.db.sql(
		f"""
		SELECT status{church_select}, type, recipient_type, recipient, request
		FROM `tabPrayer Request`
		WHERE creation > %(request_since)s
			AND status = 'answered'
			{church_condition}
		""",
		values,
		as_dict=True,
	)
