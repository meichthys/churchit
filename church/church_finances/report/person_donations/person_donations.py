import frappe

from church.utils import get_church_condition


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "collection", "fieldtype": "Link", "label": "Collection", "options": "Collection", "width": 200},
		{"fieldname": "date", "fieldtype": "Date", "label": "Date", "width": 120},
		{"fieldname": "fund", "fieldtype": "Link", "label": "Fund", "options": "Fund", "width": 150},
		{"fieldname": "payment_type", "fieldtype": "Link", "label": "Payment Type", "options": "Payment Type", "width": 120},
		{"fieldname": "check_number", "fieldtype": "Data", "label": "Check #", "width": 100},
		{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 120},
	]


def get_data(filters=None):
	filters = filters or {}
	values = {}
	church_condition = get_church_condition(filters, "`tabCollection`.church", values)

	person_condition = ""
	if filters.get("person"):
		person_condition = " AND `tabDonation`.person = %(person)s"
		values["person"] = filters["person"]

	return frappe.db.sql(
		f"""
		SELECT
			`tabCollection`.name AS collection,
			`tabCollection`.date,
			`tabDonation`.fund,
			`tabDonation`.payment_type,
			`tabDonation`.check_number,
			`tabDonation`.amount
		FROM `tabDonation`
		INNER JOIN `tabCollection` ON `tabCollection`.name = `tabDonation`.parent
		WHERE `tabDonation`.parenttype = 'Collection'
			{person_condition}
			{church_condition}
		ORDER BY `tabCollection`.date DESC
		""",
		values,
		as_dict=True,
	)
