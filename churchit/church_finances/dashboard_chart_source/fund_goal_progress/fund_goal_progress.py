import frappe


@frappe.whitelist()
def get(chart_name=None, chart=None, no_cache=None, filters=None, **kwargs):
	"""Percentage progress of each goal-bearing fund's balance toward its goal."""
	rows = frappe.db.sql(
		"""
		SELECT
			fund AS label,
			ROUND((balance / goal_amount) * 100, 1) AS progress
		FROM `tabFund`
		WHERE goal_amount > 0
		ORDER BY progress DESC
		""",
		as_dict=True,
	)
	return {
		"labels": [r["label"] for r in rows],
		"datasets": [
			{"name": "Goal Progress (%)", "values": [float(r["progress"] or 0) for r in rows]}
		],
	}
