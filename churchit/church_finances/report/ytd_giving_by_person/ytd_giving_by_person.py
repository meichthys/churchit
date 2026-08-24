import frappe
from frappe.query_builder.functions import Avg, Count, Max, Sum
from frappe.utils import cint
from pypika import Order

from churchit.query import Year
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 240},
		{"fieldname": "gift_count", "fieldtype": "Int", "label": "# Gifts", "width": 80},
		{"fieldname": "ytd_amount", "fieldtype": "Currency", "label": "YTD Amount", "width": 140},
		{"fieldname": "avg_gift", "fieldtype": "Currency", "label": "Avg Gift", "width": 120},
		{"fieldname": "last_gift_date", "fieldtype": "Date", "label": "Last Gift", "width": 110},
		{"fieldname": "prior_year_amount", "fieldtype": "Currency", "label": "Prior Year", "width": 140},
	]


def get_data(filters=None):
	year = cint((filters or {}).get("year")) or frappe.utils.now_datetime().year

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	PriorDonation = frappe.qb.DocType("Donation").as_("prior_donation")
	PriorCollection = frappe.qb.DocType("Collection").as_("prior_collection")

	prior_year_amount = (
		frappe.qb.from_(PriorDonation)
		.join(PriorCollection)
		.on(PriorCollection.name == PriorDonation.parent)
		.select(Sum(PriorDonation.amount))
		.where(
			(PriorDonation.person == Donation.person)
			& (Year(PriorCollection.date) == year - 1)
			& (PriorCollection.docstatus == 1)
		)
	)

	return (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Collection.name == Donation.parent)
		.select(
			Donation.person,
			Count("*").as_("gift_count"),
			Sum(Donation.amount).as_("ytd_amount"),
			Avg(Donation.amount).as_("avg_gift"),
			Max(Collection.date).as_("last_gift_date"),
			prior_year_amount.as_("prior_year_amount"),
		)
		.where(Donation.person.isnotnull() & (Year(Collection.date) == year) & (Collection.docstatus == 1))
		.groupby(Donation.person)
		.orderby(Sum(Donation.amount), order=Order.desc)
		.run(as_dict=True)
	)
