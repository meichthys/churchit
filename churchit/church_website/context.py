# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Website context additions, wired through the ``update_website_context`` hook."""

import frappe
from frappe import _

PORTAL_URL = "/portal"


def update_website_context(context):
	"""Put the member portal in the top-right user menu.

	Frappe builds that menu with only My Account and Log out, and its own Portal
	link on /me is shown to Website Users alone — so staff, who are System Users,
	had no route into the portal at all.
	"""
	if frappe.session.user == "Guest":
		return

	menu = context.get("post_login")
	if not isinstance(menu, list) or any(item.get("url") == PORTAL_URL for item in menu):
		return

	menu.insert(0, {"label": _("Portal"), "url": PORTAL_URL})
