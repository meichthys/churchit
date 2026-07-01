import frappe
from pypika import Order

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


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

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")

	query = (
		frappe.qb.from_(Donation)
		.inner_join(Collection)
		.on(Collection.name == Donation.parent)
		.select(
			Collection.name.as_("collection"),
			Collection.date,
			Donation.fund,
			Donation.payment_type,
			Donation.check_number,
			Donation.amount,
		)
		.where(Donation.parenttype == "Collection")
		.orderby(Collection.date, order=Order.desc)
	)

	if filters.get("person"):
		query = query.where(Donation.person == filters["person"])

	return query.run(as_dict=True)
