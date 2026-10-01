import frappe
from frappe import _
from frappe.query_builder.functions import Sum

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
			"fieldname": "collection",
			"fieldtype": "Link",
			"label": _("Collection"),
			"options": "Collection",
			"width": 180,
		},
		{"fieldname": "fund", "fieldtype": "Data", "label": _("Fund"), "width": 150},
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 150},
		{"fieldname": "payment_type", "fieldtype": "Data", "label": _("Payment Type"), "width": 120},
		{"fieldname": "check_number", "fieldtype": "Data", "label": _("Check #"), "width": 100},
		{"fieldname": "amount", "fieldtype": "Currency", "label": _("Amount"), "width": 120},
		{"fieldname": "notes", "fieldtype": "Data", "label": _("Notes"), "width": 200},
	]


def get_data(filters):
	parent_filter = (filters or {}).get("parent_filter")

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")

	query = (
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
	)
	return scoped(query, Collection, filters).run(as_dict=True)
