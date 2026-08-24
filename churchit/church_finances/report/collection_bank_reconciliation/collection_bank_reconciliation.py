import frappe
from frappe.query_builder.functions import Sum

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


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
	parent_filter = (filters or {}).get("parent_filter")

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")

	return (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Collection.name == Donation.parent)
		.select(
			Donation.parent.as_("collection"),
			Donation.fund,
			Donation.person,
			Donation.payment_type,
			Donation.check_number,
			Sum(Donation.amount).as_("amount"),
			Donation.notes,
		)
		.where(Donation.parent == parent_filter)
		.groupby(Donation.check_number)
		.run(as_dict=True)
	)
