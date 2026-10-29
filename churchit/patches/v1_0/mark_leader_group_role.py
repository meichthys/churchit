# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Tick Leads the Group on the starter "Leader" Group Role, so its people lead their groups."""

import frappe


def execute():
	if frappe.db.exists("Group Role", "Leader"):
		frappe.db.set_value("Group Role", "Leader", "is_leader", 1)
