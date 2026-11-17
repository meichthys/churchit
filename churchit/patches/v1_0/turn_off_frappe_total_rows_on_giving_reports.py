# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Turn off Frappe's total row on Budget vs Actual and YTD Giving by Person, which add their own.

Migrate keeps a report's Add Total Row as the site has it, so the shipped value reaches only new sites.
Without this patch an existing site shows two Total rows, and the second one counts the first.
"""

import frappe

REPORTS = ("Budget vs Actual", "YTD Giving by Person")


def execute():
	for report in REPORTS:
		if frappe.db.get_value("Report", report, "add_total_row"):
			frappe.db.set_value("Report", report, "add_total_row", 0)
