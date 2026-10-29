# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Add the Personal Details and Care Request forms to the portal menu on existing sites.

Both forms shipped without a menu row, so members could reach them only by typing the address.
Adds just the missing rows and leaves the rest of the menu as the site admin left it.
"""

import frappe

ITEMS = (
	{"title": "Personal Details", "route": "personal-details", "reference_doctype": "Person"},
	{"title": "Care Requests", "route": "care-request", "reference_doctype": "Care Request"},
)


def execute():
	settings = frappe.get_doc("Portal Settings")
	routes = {row.route for row in settings.menu}
	missing = [item for item in ITEMS if item["route"] not in routes]
	if not missing:
		return

	for item in missing:
		settings.add_item({**item, "role": "Church User"})
	settings.save(ignore_permissions=True)
