# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Add the Giving Statements page to the member portal menu on existing sites.

The portal menu is seeded by after_install, which only ever runs when the app is
first installed, so a site that predates the Giving Statement doctype has no way
to reach /statements. Adds just that one row and leaves the rest of the menu — and
default_portal_home — as the site admin left it.
"""

import frappe

ROUTE = "statements"


def execute():
	if not frappe.db.exists("DocType", "Giving Statement"):
		return

	settings = frappe.get_doc("Portal Settings")
	if any(row.route == ROUTE for row in settings.menu):
		return

	settings.add_item(
		{
			"title": "Giving Statements",
			"route": ROUTE,
			"reference_doctype": "Giving Statement",
			"role": "Church User",
		}
	)
	settings.save(ignore_permissions=True)
