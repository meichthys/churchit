# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Point the portal menu's Newsletter Subscription item at the Communication Preferences page.

The preferences page replaced the newsletter subscription page. The row keeps its place,
its role and whether it is on, as the site admin left them.
"""

import frappe

OLD_ROUTE = "newsletter-subscription"
ITEM = {
	"title": "Communication Preferences",
	"route": "preferences",
	"reference_doctype": "Communication Consent",
}


def execute():
	settings = frappe.get_doc("Portal Settings")
	rows = [row for row in settings.get_all_menu_items() if (row.route or "").strip("/") == OLD_ROUTE]
	if not rows:
		return

	for row in rows:
		row.update(ITEM)
	settings.save(ignore_permissions=True)
