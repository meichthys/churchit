import frappe
from frappe import _
from frappe.utils import add_days
from pypika import Order

from churchit.church_scope import get_church_columns, scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = [*get_columns(filters), *get_church_columns(filters)]
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	columns = [
		{
			"fieldname": "collection",
			"fieldtype": "Link",
			"label": _("Collection"),
			"options": "Collection",
			"width": 200,
		},
		{"fieldname": "date", "fieldtype": "Date", "label": _("Date"), "width": 120},
		{"fieldname": "fund", "fieldtype": "Link", "label": _("Fund"), "options": "Fund", "width": 150},
		{
			"fieldname": "payment_type",
			"fieldtype": "Link",
			"label": _("Payment Type"),
			"options": "Payment Type",
			"width": 120,
		},
		{"fieldname": "check_number", "fieldtype": "Data", "label": _("Check #"), "width": 100},
		{"fieldname": "amount", "fieldtype": "Currency", "label": _("Amount"), "width": 120},
	]
	if (filters or {}).get("person"):
		return columns

	person = {
		"fieldname": "person",
		"fieldtype": "Link",
		"label": _("Person"),
		"options": "Person",
		"width": 180,
	}
	return [person, *columns]


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
			Donation.person,
			Collection.date,
			Collection.church,
			Donation.fund,
			Donation.payment_type,
			Donation.check_number,
			Donation.amount,
		)
		.where((Donation.parenttype == "Collection") & (Collection.docstatus == 1))
		.orderby(Collection.date, order=Order.desc)
	)

	if filters.get("person"):
		query = query.where(Donation.person == filters["person"])
	if filters.get("from_date"):
		query = query.where(Collection.date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(Collection.date < add_days(filters["to_date"], 1))

	return scoped(query, Collection, filters).run(as_dict=True)
