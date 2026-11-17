# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Remove the shipped Prayer Request New and Alms Request Review Notifications. The inserted ones replace them."""

import frappe

DUPLICATES = ("Prayer Request New", "Alms Request Review")


def execute():
	for name in DUPLICATES:
		if frappe.db.get_value("Notification", name, "is_standard"):
			frappe.delete_doc("Notification", name, force=True, ignore_permissions=True)
