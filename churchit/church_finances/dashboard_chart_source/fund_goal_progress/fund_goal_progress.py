import frappe
from pypika import Field, Order

from churchit.query import Round


@frappe.whitelist()
def get(chart_name=None, chart=None, no_cache=None, filters=None, **kwargs):
	"""Goal amount next to current balance for each goal-bearing fund."""
	Fund = frappe.qb.DocType("Fund")
	rows = (
		frappe.qb.from_(Fund)
		.select(
			Fund.fund.as_("label"),
			Fund.balance,
			Fund.goal_amount,
			Round((Fund.balance / Fund.goal_amount) * 100, 1).as_("progress"),
		)
		.where(Fund.goal_amount > 0)
		.orderby(Field("progress"), order=Order.desc)
		.run(as_dict=True)
	)
	return {
		"labels": [r["label"] for r in rows],
		"datasets": [
			{"name": "Balance", "values": [float(r["balance"] or 0) for r in rows]},
			{"name": "Goal Amount", "values": [float(r["goal_amount"] or 0) for r in rows]},
		],
	}
