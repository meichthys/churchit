# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give each group saved without a name its ID as name, so that its next save passes the Name check."""

import frappe


def execute():
	# church-scope: a patch names the groups of every church
	for name in frappe.get_all("Group", filters={"group_name": ("is", "not set")}, pluck="name"):
		frappe.db.set_value("Group", name, "group_name", name, update_modified=False)
