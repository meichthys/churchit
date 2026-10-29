# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Add the Lead a Group page to the member portal menu on existing sites.

after_install seeds the menu only on a new site. Adds just that one row and leaves the rest of the
menu as the site admin left it.
"""

import frappe

ROUTE = "group-leader"


def execute():
	settings = frappe.get_doc("Portal Settings")
	if any(row.route == ROUTE for row in settings.menu):
		return

	settings.add_item(
		{"title": "Lead a Group", "route": ROUTE, "reference_doctype": "Group", "role": "Church User"}
	)
	settings.save(ignore_permissions=True)
