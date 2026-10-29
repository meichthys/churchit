# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Delete the New Members by Month chart, an exact copy of the Members chart that no workspace showed.

A site that put it on a workspace or dashboard of its own keeps it.
"""

import frappe

CHART = "New Members by Month"


def execute():
	if not frappe.db.exists("Dashboard Chart", CHART):
		return
	if frappe.db.exists("Workspace Chart", {"chart_name": CHART}) or frappe.db.exists(
		"Dashboard Chart Link", {"chart": CHART}
	):
		return
	frappe.delete_doc("Dashboard Chart", CHART, ignore_permissions=True, force=True)
