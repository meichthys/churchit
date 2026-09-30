import frappe
from frappe.query_builder.functions import Coalesce, Sum
from pypika import Order

from churchit.church_scope import scoped


@frappe.whitelist()
def get(
	chart_name: str | None = None,
	chart: str | dict | None = None,
	no_cache: bool | int | None = None,
	filters: str | list | dict | None = None,
	**kwargs,
):
	frappe.has_permission("Collection", "report", throw=True)
	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	Fund = frappe.qb.DocType("Fund")

	query = (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Collection.name == Donation.parent)
		.left_join(Fund)
		.on(Fund.name == Donation.fund)
		.select(
			Coalesce(Fund.fund, Donation.fund).as_("label"),
			Sum(Donation.amount).as_("total"),
		)
		.where((Collection.docstatus == 1) & Donation.fund.isnotnull())
		.groupby(Donation.fund)
		.orderby(Sum(Donation.amount), order=Order.desc)
		.limit(10)
	)
	rows = scoped(query, Collection, {}).run(as_dict=True)
	return {
		"labels": [r["label"] for r in rows],
		"datasets": [{"name": "Giving by Fund", "values": [float(r["total"] or 0) for r in rows]}],
	}
