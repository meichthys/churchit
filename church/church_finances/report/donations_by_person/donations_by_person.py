import frappe
from frappe.query_builder.functions import Sum
from pypika import Order

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
		{"fieldname": "total_amount", "fieldtype": "Currency", "label": "Total Amount", "width": 150},
	]


def get_data(filters=None):
	filters = filters or {}

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	total_amount = Sum(Donation.amount).as_("total_amount")

	query = (
		frappe.qb.from_(Donation)
		.inner_join(Collection)
		.on(Collection.name == Donation.parent)
		.select(Donation.person, total_amount)
		.where((Donation.parenttype == "Collection") & Donation.person.isnotnull())
		.groupby(Donation.person)
		.orderby(Sum(Donation.amount), order=Order.desc)
	)

	if filters.get("from_date"):
		query = query.where(Collection.date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(Collection.date <= filters["to_date"])

	return query.run(as_dict=True)
