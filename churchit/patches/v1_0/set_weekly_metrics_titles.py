# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Title each Weekly Metrics row with the first day of its week instead of the church ID and the date."""

import frappe

from churchit.church_summary.doctype.weekly_metrics.weekly_metrics import get_title


def execute():
	for row in frappe.get_all("Weekly Metrics", fields=["name", "week_start", "church"]):
		title = get_title(row.week_start, row.church)
		frappe.db.set_value("Weekly Metrics", row.name, "title", title, update_modified=False)
