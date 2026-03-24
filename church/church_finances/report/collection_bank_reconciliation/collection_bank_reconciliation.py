import frappe

from church.utils import get_church_condition


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "collection", "fieldtype": "Link", "label": "Collection", "options": "Collection", "width": 180},
		{"fieldname": "fund", "fieldtype": "Data", "label": "Fund", "width": 150},
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 150},
		{"fieldname": "payment_type", "fieldtype": "Data", "label": "Payment Type", "width": 120},
		{"fieldname": "check_number", "fieldtype": "Data", "label": "Check #", "width": 100},
		{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 120},
		{"fieldname": "notes", "fieldtype": "Data", "label": "Notes", "width": 200},
	]


def get_data(filters):
	filters = filters or {}
	values = {"parent_filter": filters.get("parent_filter")}
	church_condition = get_church_condition(filters, "`tabCollection`.church", values)

	return frappe.db.sql(
		f"""
		SELECT
			`tabDonation`.parent as collection,
			`tabDonation`.fund,
			`tabDonation`.person,
			`tabDonation`.payment_type,
			`tabDonation`.check_number,
			sum(`tabDonation`.amount) as amount,
			`tabDonation`.notes
		FROM `tabDonation`
		INNER JOIN `tabCollection` ON `tabCollection`.name = `tabDonation`.parent
		WHERE `tabDonation`.parent = %(parent_filter)s
			{church_condition}
		GROUP BY check_number
		""",
		values,
		as_dict=True,
	)
