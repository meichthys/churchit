import frappe

from churchit.church_website.menu import get_route
from churchit.church_website.pages import is_public_website_on
from churchit.church_website.published_fields import get_reachable_field_map


@frappe.whitelist(allow_guest=False, methods=["GET", "POST"])
def get_published_fields(doctype: str | None = None) -> dict:
	"""Where the website shows each field, as ``{doctype: {fieldname: [source, …]}}``. Reads only.

	*doctype* narrows the answer to that doctype's fields, which is what a
	browser still running a cached copy of the badge script asks for.
	"""
	frappe.only_for(["Church Manager", "System Manager"])
	published = get_reachable_field_map()
	return published.get(doctype, {}) if doctype else published


@frappe.whitelist(allow_guest=False, methods=["GET", "POST"])
def get_published_web_page(url: str | None) -> dict | None:
	"""The published Web Page a navbar or footer link points at, or None. Reads only.

	Only site-relative links can name a Web Page; www/ pages and external links
	have nothing to un-publish.
	"""
	frappe.only_for(["Church Manager", "System Manager"])
	route = get_route(url)
	if not route:
		return None
	return frappe.db.get_value(
		"Web Page", {"route": route, "published": 1}, ["name", "title", "route"], as_dict=True
	)


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_website_home_page() -> str | None:
	"""The page a visitor lands on at /, or None while the public website is off. Reads only.

	The desk's website preview shows it. The route is public, but Website Settings is not readable
	by every desk user.
	A site without a home page sends a visitor to the login page, as Frappe does.
	"""
	if not is_public_website_on():
		return None
	return frappe.db.get_single_value("Website Settings", "home_page") or "login"
