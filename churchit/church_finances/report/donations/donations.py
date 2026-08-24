import frappe
from pypika import Order

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Collection", "options": "Collection", "width": 200},
		{"fieldname": "function", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 200},
		{"fieldname": "fund", "fieldtype": "Link", "label": "Fund", "options": "Fund", "width": 150},
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 150},
		{"fieldname": "payment_type", "fieldtype": "Link", "label": "Payment Type", "options": "Payment Type", "width": 120},
		{"fieldname": "check_number", "fieldtype": "Data", "label": "Check #", "width": 100},
		{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 120},
	]


def get_data():
	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")

	return (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Collection.name == Donation.parent)
		.select(
			Collection.name,
			Collection.function,
			Donation.fund,
			Donation.person,
			Donation.payment_type,
			Donation.check_number,
			Donation.amount,
		)
		.where(Donation.parenttype == "Collection")
		.orderby(Collection.modified, order=Order.desc)
		.run(as_dict=True)
	)
