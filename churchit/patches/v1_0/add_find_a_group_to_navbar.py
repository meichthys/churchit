# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Add Find a Group to the website navbar on existing sites, after Ministries.

after_install seeds the navbar only on a new site. Adds just that one row and leaves the rest of the
navbar as the site admin left it.
"""

import frappe

FIND_A_GROUP = {"label": "Find a Group", "url": "/find-a-group"}
ANCHOR = "/ministries"


def execute():
	settings = frappe.get_doc("Website Settings")
	routes = [(row.url or "").rstrip("/") for row in settings.top_bar_items]
	if FIND_A_GROUP["url"] in routes:
		return

	item = settings.append("top_bar_items", {**FIND_A_GROUP, "right": 1})
	if ANCHOR in routes:
		settings.top_bar_items.remove(item)
		settings.top_bar_items.insert(routes.index(ANCHOR) + 1, item)
	for position, row in enumerate(settings.top_bar_items, start=1):
		row.idx = position
	settings.save(ignore_permissions=True)
