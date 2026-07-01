import frappe


@frappe.whitelist()
def get(chart_name=None, chart=None, no_cache=None, filters=None, **kwargs):
	rows = frappe.db.sql(
		"""
		SELECT COALESCE(f.fund, d.fund) AS label, SUM(d.amount) AS total
		FROM `tabDonation` d
		JOIN `tabCollection` c ON c.name = d.parent
		LEFT JOIN `tabFund` f ON f.name = d.fund
		WHERE c.docstatus = 1 AND d.fund IS NOT NULL
		GROUP BY d.fund
		ORDER BY total DESC
		LIMIT 10
		""",
		as_dict=True,
	)
	return {
		"labels": [r["label"] for r in rows],
		"datasets": [{"name": "Giving by Fund", "values": [float(r["total"] or 0) for r in rows]}],
	}
