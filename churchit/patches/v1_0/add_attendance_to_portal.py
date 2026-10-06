# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Add the member's Attendance page to the portal menu on existing sites.

The portal menu is seeded by after_install, which only runs when the app is
first installed. Adds just that one row and leaves the rest of the menu as the
site admin left it.
"""

import frappe

ROUTE = "attendance"


def execute():
	settings = frappe.get_doc("Portal Settings")
	if any(row.route == ROUTE for row in settings.menu):
		return

	settings.add_item(
		{
			"title": "Attendance",
			"route": ROUTE,
			"reference_doctype": "Function Attendance",
			"role": "Church User",
		}
	)
	settings.save(ignore_permissions=True)
