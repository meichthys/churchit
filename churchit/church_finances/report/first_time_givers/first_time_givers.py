import frappe
from frappe.query_builder.functions import Min
from frappe.utils import cint
from pypika import Field, Interval, Order

from churchit.query import CurDate
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 240},
		{"fieldname": "first_gift_date", "fieldtype": "Date", "label": "First Gift", "width": 120},
		{"fieldname": "first_gift_amount", "fieldtype": "Currency", "label": "First Gift Amount", "width": 160},
	]


def get_data(filters=None):
	window_days = cint((filters or {}).get("window_days", 90)) or 90

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	FirstDonation = frappe.qb.DocType("Donation").as_("first_donation")
	FirstCollection = frappe.qb.DocType("Collection").as_("first_collection")

	first_gift_amount = (
		frappe.qb.from_(FirstDonation)
		.join(FirstCollection)
		.on(FirstCollection.name == FirstDonation.parent)
		.select(FirstDonation.amount)
		.where((FirstDonation.person == Donation.person) & (FirstCollection.docstatus == 1))
		.orderby(FirstCollection.date)
		.limit(1)
	)

	return (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Collection.name == Donation.parent)
		.select(
			Donation.person,
			Min(Collection.date).as_("first_gift_date"),
			first_gift_amount.as_("first_gift_amount"),
		)
		.where(Donation.person.isnotnull() & (Collection.docstatus == 1))
		.groupby(Donation.person)
		.having(Field("first_gift_date") >= CurDate() - Interval(days=window_days))
		.orderby(Field("first_gift_date"), order=Order.desc)
		.run(as_dict=True)
	)
