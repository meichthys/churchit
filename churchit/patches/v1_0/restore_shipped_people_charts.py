# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Replace the People and Members charts that install made with the ones the app ships.

Install made its own copies before the shipped charts were imported, and a copy newer than the
file is never replaced, so a site installed since then counted every church's people and
memberships rather than only the reader's.
"""

import frappe

CHARTS = ("People", "Members")


def execute():
	for chart in CHARTS:
		if frappe.db.get_value("Dashboard Chart", chart, "is_standard") == 0:
			frappe.reload_doc("Church People", "dashboard_chart", frappe.scrub(chart), force=True)
