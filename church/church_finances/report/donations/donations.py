import frappe

from church.utils import get_church_condition, set_report_link_titles


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = [
		{"fieldname": "name", "fieldtype": "Link", "label": "Collection", "options": "Collection", "width": 200},
	]
	cols += [
		{"fieldname": "function", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 200},
		{"fieldname": "fund", "fieldtype": "Link", "label": "Fund", "options": "Fund", "width": 150},
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 150},
		{"fieldname": "payment_type", "fieldtype": "Link", "label": "Payment Type", "options": "Payment Type", "width": 120},
		{"fieldname": "check_number", "fieldtype": "Data", "label": "Check #", "width": 100},
		{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 120},
	]
	return cols


def get_data(filters=None):
	values = {}
	church_condition = get_church_condition(filters, "Collection", "`tabCollection`.`name`", values)

	return frappe.db.sql(
		f"""
		SELECT
			`tabCollection`.name,
			`tabCollection`.function,
			`tabDonation`.fund,
			`tabDonation`.person,
			`tabDonation`.payment_type,
			`tabDonation`.check_number,
			`tabDonation`.amount
		FROM `tabDonation`
		INNER JOIN `tabCollection` ON `tabCollection`.name = `tabDonation`.parent
		WHERE `tabDonation`.parenttype = 'Collection'
			{church_condition}
		ORDER BY `tabCollection`.modified DESC
		""",
		values,
		as_dict=True,
	)
