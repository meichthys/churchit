import frappe
from pypika import Field, Order

from churchit.query import Round


@frappe.whitelist()
def get(chart_name=None, chart=None, no_cache=None, filters=None, **kwargs):
	"""Percentage progress of each goal-bearing fund's balance toward its goal."""
	Fund = frappe.qb.DocType("Fund")
	rows = (
		frappe.qb.from_(Fund)
		.select(
			Fund.fund.as_("label"),
			Round((Fund.balance / Fund.goal_amount) * 100, 1).as_("progress"),
		)
		.where(Fund.goal_amount > 0)
		.orderby(Field("progress"), order=Order.desc)
		.run(as_dict=True)
	)
	return {
		"labels": [r["label"] for r in rows],
		"datasets": [
			{"name": "Goal Progress (%)", "values": [float(r["progress"] or 0) for r in rows]}
		],
	}
