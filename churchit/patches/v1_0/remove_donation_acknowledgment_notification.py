# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Remove the shipped Donation Acknowledgment Notification: a Giving Settings check now emails each giver a receipt."""

import frappe

NAME = "Donation Acknowledgment"


def execute():
	"""Delete only the standard record. A church's own copy has no standard flag and stays."""
	if frappe.db.get_value("Notification", NAME, "is_standard"):
		frappe.delete_doc("Notification", NAME, force=True)
