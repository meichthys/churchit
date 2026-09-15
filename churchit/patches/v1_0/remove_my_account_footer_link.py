# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Drop the shipped "My Account" link from the website footer on existing sites.

The navbar's account dropdown already leads to /me, so the footer repeats it.
Only the row this app shipped is removed; a renamed or re-pointed entry stays.
"""

import frappe

MY_ACCOUNT = {"label": "My Account", "url": "/me"}


def execute():
	settings = frappe.get_doc("Website Settings")
	shipped = [
		row
		for row in settings.footer_items
		if row.label == MY_ACCOUNT["label"] and (row.url or "").rstrip("/") == MY_ACCOUNT["url"]
	]
	if not shipped:
		return
	for row in shipped:
		settings.footer_items.remove(row)
	for position, row in enumerate(settings.footer_items, start=1):
		row.idx = position
	settings.save(ignore_permissions=True)
