# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give each fund transfer out of a shared fund the church of whoever made it.

A transfer took its church from the source fund, so a shared fund left it empty, which shared the
transfer with every church. A transfer now keeps the church that moved the money.
"""

import frappe

from churchit.church_scope import default_church, is_multi_church


def execute():
	if not is_multi_church():
		return
	transfers = frappe.get_all(
		"Fund Transfer", filters={"church": ("is", "not set")}, fields=["name", "owner"]
	)
	for transfer in transfers:
		frappe.db.set_value(
			"Fund Transfer", transfer.name, "church", default_church(transfer.owner), update_modified=False
		)
