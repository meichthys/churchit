# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/bulletins"
		raise frappe.Redirect

	context.no_cache = 1
	context.title = _("Bulletins")
	context.bulletins = get_published_bulletins()


def get_published_bulletins():
	"""Bulletins marked for the portal, newest function first."""
	return frappe.get_all(
		"Bulletin",
		filters={"publish": 1},
		fields=["name", "function_name", "function_date"],
		order_by="function_date desc",
	)
