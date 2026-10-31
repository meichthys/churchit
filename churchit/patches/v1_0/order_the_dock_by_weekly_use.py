# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Put the site's arrangement of the Churchit dock in the order Churchit ships, unless someone moved it.

Church Features saves an arrangement of the dock to hide a disabled module, and a saved
arrangement keeps its own order, so the shipped order reaches such a site only through this patch.
"""

import frappe
from frappe.desk.doctype.dock.dock import get_app_dock

PREVIOUS_ORDER = [
	"Summary",
	"People",
	"Ministries",
	"Prayers",
	"Study",
	"Communications",
	"Missions",
	"Finances",
	"Operations",
	"Foundations",
	"Web Site",
	"Settings",
	"Help",
]


def execute():
	name = frappe.db.get_value("Dock", {"app": "churchit", "standard": 0, "user": ""})
	if not name:
		return

	dock = frappe.get_doc("Dock", name)
	if [row.link_to for row in dock.items] != PREVIOUS_ORDER:
		return

	shipped = [entry["link_to"] for entry in get_app_dock("churchit")]
	dock.items.sort(key=lambda row: shipped.index(row.link_to))
	for idx, row in enumerate(dock.items, start=1):
		row.idx = idx
	dock.save(ignore_permissions=True)
