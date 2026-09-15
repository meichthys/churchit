# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Bring existing sites up to the Bulletin feature.

Seeds the default leadership roles in Bulletin Settings, adds the Bulletins page
to the member portal menu, and removes the Sunday Bulletin print format on
Function that the Bulletin doctype replaces. after_install does the first two
for new sites but only ever runs once.
"""

import frappe

from churchit.patches.after_install import setup_bulletin_settings

ROUTE = "bulletins"


def execute():
	frappe.delete_doc_if_exists("Print Format", "Sunday Bulletin")
	setup_bulletin_settings()
	add_bulletins_to_portal()


def add_bulletins_to_portal():
	settings = frappe.get_doc("Portal Settings")
	if any(row.route == ROUTE for row in settings.menu):
		return
	settings.add_item(
		{"title": "Bulletins", "route": ROUTE, "reference_doctype": "Bulletin", "role": "Church User"}
	)
	settings.save(ignore_permissions=True)
