# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Group Meeting Function Type that a group's Set Up Meetings uses."""

import frappe


def execute():
	if not frappe.db.exists("Function Type", "Group Meeting"):
		frappe.get_doc({"doctype": "Function Type", "type": "Group Meeting"}).insert(ignore_permissions=True)
