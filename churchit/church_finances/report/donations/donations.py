import frappe
from frappe import _
from pypika import Order

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
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


def get_data(filters=None):
	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")

	query = (
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
		# A cancelled collection took its gifts back.
		.where((Donation.parenttype == "Collection") & (Collection.docstatus < 2))
		.orderby(Collection.modified, order=Order.desc)
	)
	return scoped(query, Collection, filters).run(as_dict=True)
