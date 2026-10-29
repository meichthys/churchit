# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Add the My Household and Member Directory pages to the portal menu on existing sites.

Adds just the missing rows and leaves the rest of the menu as the site admin left it. The Member Directory
row shows only while People Settings turns the page on.
"""

import frappe

from churchit.church_people.doctype.people_settings.people_settings import sync_directory_menu_item

ITEMS = (
	{"title": "My Household", "route": "household", "reference_doctype": "Family"},
	{"title": "Member Directory", "route": "directory", "reference_doctype": "Person"},
)


def execute():
	settings = frappe.get_single("Portal Settings")
	routes = {(row.route or "").strip("/") for row in settings.get_all_menu_items()}
	missing = [item for item in ITEMS if item["route"] not in routes]
	if missing:
		for item in missing:
			settings.add_item({**item, "role": "Church User"})
		settings.save(ignore_permissions=True)
	sync_directory_menu_item()
