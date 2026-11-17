import frappe
from frappe import _
from frappe.utils import flt

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	if data and data[0].docstatus == 2:
		message = _(
			"This collection is cancelled. Its gifts are not in the fund balances or the giving totals."
		)
		return columns, data, f'<span class="text-danger">{message}</span>'
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
		{"fieldname": "fund", "fieldtype": "Link", "label": _("Fund"), "options": "Fund", "width": 150},
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 150},
		{"fieldname": "payment_type", "fieldtype": "Data", "label": _("Payment Type"), "width": 120},
		{"fieldname": "check_number", "fieldtype": "Data", "label": _("Check #"), "width": 100},
		{"fieldname": "amount", "fieldtype": "Currency", "label": _("Amount"), "width": 120},
		{"fieldname": "notes", "fieldtype": "Data", "label": _("Notes"), "width": 200},
	]


def get_data(filters):
	"""One line per bank item: a check by giver and number (a split check stays one line), and every other
	payment by payment type and fund, as one cash count or one online deposit. Donated property is no bank item."""
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
			Donation.amount,
			Donation.notes,
			Collection.docstatus,
		)
		.where((Donation.parent == parent_filter) & (Donation.is_non_cash == 0))
		.orderby(Donation.idx)
	)
	rows = scoped(query, Collection, filters).run(as_dict=True)

	items = {}
	for row in rows:
		if row.check_number:
			key = ("check", row.person, row.check_number)
		else:
			key = ("other", row.payment_type, row.fund)

		item = items.setdefault(key, frappe._dict(row, amount=0))
		item["amount"] += flt(row.amount)
		for fieldname in ("fund", "person", "notes"):
			if item[fieldname] != row[fieldname]:
				item[fieldname] = None
	return list(items.values())
