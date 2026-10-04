# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Take Frappe's Knowledge Base (Help Articles) out of the app on existing sites.

The documentation replaces it. Removes what this app added: the portal menu
row, the workspace number cards and the members' read permission. Articles a
church wrote stay in the desk. Their property setters stay too, because they
hide the articles from guests and Frappe's own default would publish them.
"""

import frappe

KNOWLEDGE_BASE = ("Help Article", "Help Category")
NUMBER_CARDS = ("Help Articles", "Help Categories")


def execute():
	remove_portal_menu_rows()
	for card in NUMBER_CARDS:
		frappe.delete_doc("Number Card", card, ignore_missing=True, force=True)
	frappe.db.delete("Custom DocPerm", {"parent": ("in", KNOWLEDGE_BASE), "role": "Church User"})
	for doctype in KNOWLEDGE_BASE:
		frappe.clear_cache(doctype=doctype)


def remove_portal_menu_rows():
	settings = frappe.get_doc("Portal Settings")
	rows = [row for row in settings.menu + settings.custom_menu if row.reference_doctype in KNOWLEDGE_BASE]
	if not rows:
		return
	for row in rows:
		settings.remove(row)
	settings.save(ignore_permissions=True)
