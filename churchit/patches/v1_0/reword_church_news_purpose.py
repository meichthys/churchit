# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Reword the Church News purpose so that members do not read the doctype name.

Only a copy that still has the shipped text changes. A church's own words stay.
"""

import frappe

SHIPPED = "Church Emails: news, events and announcements sent to the congregation."
REWORDED = "News, events and announcements the church sends to everyone."


def execute():
	if frappe.db.get_value("Communication Purpose", "Church News", "description") == SHIPPED:
		frappe.db.set_value("Communication Purpose", "Church News", "description", REWORDED)
