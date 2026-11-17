import frappe
from frappe import _
from frappe.utils import add_days, flt
from pypika import Field, Order

from churchit.church_scope import get_church_columns, scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = [*get_columns(), *get_church_columns(filters)]
	data = get_data(filters)
	set_report_link_titles(columns, data)
	if data:
		data.append(get_total_row(data))
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "name",
			"fieldtype": "Link",
			"label": _("Collection"),
			"options": "Collection",
			"width": 200,
		},
		{"fieldname": "date", "fieldtype": "Date", "label": _("Date"), "width": 100},
		{
			"fieldname": "function",
			"fieldtype": "Link",
			"label": _("Function"),
			"options": "Function",
			"width": 200,
		},
		{"fieldname": "fund", "fieldtype": "Link", "label": _("Fund"), "options": "Fund", "width": 150},
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 150},
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


def get_total_row(rows):
	return frappe._dict(name=_("Total"), amount=sum(flt(row.amount) for row in rows), is_total_row=1)


def get_data(filters=None):
	filters = filters or {}

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")

	query = (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Collection.name == Donation.parent)
		.select(
			Collection.name,
			Collection.date,
			Collection.function,
			Collection.church,
			Donation.fund,
			Donation.person,
			Donation.payment_type,
			Donation.check_number,
			Donation.amount,
		)
		.where((Donation.parenttype == "Collection") & (Collection.docstatus == 1))
		.orderby(Collection.date, order=Order.desc)
		.orderby(Collection.name, order=Order.desc)
	)

	if filters.get("from_date"):
		query = query.where(Collection.date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(Collection.date < add_days(filters["to_date"], 1))
	for fieldname in ("fund", "payment_type", "person"):
		if filters.get(fieldname):
			query = query.where(Field(fieldname, table=Donation) == filters[fieldname])

	return scoped(query, Collection, filters).run(as_dict=True)
