# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Stop a church's copy of Function Reminder 24h from reminding of a recurring template.

A template is only a rule and its first occurrence falls on the same date, so the copy would send two
reminders. A copy changes only while its condition is still the shipped one.
"""

import frappe

OLD_CONDITION = "doc.publish"
NEW_CONDITION = "doc.publish and not doc.auto_repeat"


def execute():
	for name in frappe.get_all(
		"Notification",
		filters={
			"is_standard": 0,
			"document_type": "Function",
			"event": "Days Before",
			"condition": OLD_CONDITION,
		},
		pluck="name",
	):
		frappe.db.set_value("Notification", name, "condition", NEW_CONDITION)
