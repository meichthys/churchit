import frappe
from frappe import _
from frappe.query_builder.functions import Min, Sum
from frappe.utils import add_days, cint, getdate, today
from pypika import Field, Order

from churchit.church_scope import scoped
from churchit.query import Date
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 240},
		{"fieldname": "first_gift_date", "fieldtype": "Date", "label": _("First Gift"), "width": 120},
		{
			"fieldname": "first_gift_amount",
			"fieldtype": "Currency",
			"label": _("First Gift Amount"),
			"width": 160,
		},
	]


def get_data(filters=None):
	"""People whose first cash gift falls in the window. The first gift is everything they gave on that day, so a check
	split across funds counts whole."""
	window_days = cint((filters or {}).get("window_days", 90)) or 90
	since = add_days(getdate(today()), -window_days)

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")

	query = (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Collection.name == Donation.parent)
		.select(Donation.person, Min(Collection.date).as_("first_gift_date"))
		.where(is_cash_gift(Donation, Collection))
		.groupby(Donation.person)
		.having(Field("first_gift_date") >= since)
		.orderby(Field("first_gift_date"), order=Order.desc)
	)
	rows = scoped(query, Collection, filters).run(as_dict=True)

	amounts = get_amounts_by_day([row.person for row in rows], since, filters)
	for row in rows:
		row.first_gift_amount = amounts.get((row.person, getdate(row.first_gift_date)))
	return rows


def get_amounts_by_day(people: list[str], since, filters) -> dict:
	"""{(person, day): the cash the person gave that day}, from *since* on."""
	if not people:
		return {}

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	day = Date(Collection.date)
	query = (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Collection.name == Donation.parent)
		.select(Donation.person, day, Sum(Donation.amount))
		.where(is_cash_gift(Donation, Collection) & Donation.person.isin(people) & (Collection.date >= since))
		.groupby(Donation.person, day)
	)
	return {(person, on): amount for person, on, amount in scoped(query, Collection, filters).run()}


def is_cash_gift(donation, collection):
	return donation.person.isnotnull() & (donation.is_non_cash == 0) & (collection.docstatus == 1)
