# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give an empty website footer the Connection Card, anonymous prayer request and portal links.

No menu linked those guest pages. A footer that already has links belongs to the church and stays
as it is, and so does a footer that someone emptied: Website Settings keeps a Version of each save,
and one that removed footer links shows that the footer is empty on purpose.
"""

import json

import frappe

from churchit.patches.after_install import FOOTER_ITEMS


def execute():
	settings = frappe.get_doc("Website Settings")
	if settings.footer_items or is_footer_emptied():
		return

	for item in FOOTER_ITEMS:
		settings.append("footer_items", item)
	settings.save(ignore_permissions=True)


def is_footer_emptied() -> bool:
	"""Whether a saved change to Website Settings removed footer links."""
	changes = frappe.get_all(
		"Version",
		filters={"ref_doctype": "Website Settings", "data": ("like", '%"footer_items"%')},
		pluck="data",
	)
	return any(row[0] == "footer_items" for data in changes for row in json.loads(data).get("removed") or [])
