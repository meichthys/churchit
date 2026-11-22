# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The page that holds the member app (frontend/), for /portal and every path under it.

frontend/ builds member_portal.html (see hooks.py website_route_rules). Each user's page holds their own
CSRF token and boot, so it never enters Frappe's page cache, which is keyed by path alone.
"""

from urllib.parse import quote

import frappe
from frappe.utils import escape_html

from churchit.portal.boot import get_boot

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + quote(get_requested_path())
		raise frappe.Redirect(302)

	context.no_cache = 1
	context.boot = get_boot()
	favicon = context.get("favicon") or "/assets/churchit/icons/favicon.ico"
	context.favicon_link = f'<link rel="icon" href="{escape_html(favicon)}">'


def get_requested_path() -> str:
	"""The path and query string the guest asked for (Frappe's request.full_path always ends in "?")."""
	request = frappe.request
	query = frappe.safe_decode(request.query_string) if request.query_string else ""
	return request.path + ("?" + query if query else "")
