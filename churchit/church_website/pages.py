# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A page renderer and a Web Page extension that keep members-only Web Pages from guests."""

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.website.page_renderers.base_renderer import BaseRenderer
from frappe.website.router import evaluate_dynamic_routes
from frappe.www import list as portal_list
from werkzeug.routing import Rule

from churchit.church_scope import session_person
from churchit.www.directory import is_directory_member


class MembersOnlyPage(BaseRenderer):
	"""The login page for a Guest, and 403 for a non-member, on a members-only Web Page.

	A renderer runs before Frappe's page cache, so a page a member viewed is never served from the
	cache to anyone else.
	"""

	def can_render(self):
		return is_members_only(self.path) and not can_open_members_only_pages()

	def render(self):
		if frappe.session.user == "Guest":
			frappe.flags.redirect_location = "/login?" + urlencode({"redirect-to": "/" + self.path}, safe="/")
			raise frappe.Redirect
		raise frappe.PermissionError(_("This page is for members only."))


def is_members_only(route: str) -> bool:
	"""True when *route* is a published members-only Web Page, or a path its dynamic route matches."""
	# Before migrate adds the field, no page is members-only.
	if not frappe.get_meta("Web Page").has_field("members_only"):
		return False

	# Frappe finds a Web Page by route with a case and accent insensitive lookup, so match the same way.
	if frappe.db.exists("Web Page", {"route": route, "published": 1, "members_only": 1}):
		return True

	pages = frappe.get_all(
		"Web Page", filters={"published": 1, "members_only": 1, "dynamic_route": 1}, fields=["name", "route"]
	)
	rules = [Rule(f"/{page.route}", endpoint=page.name) for page in pages]
	return bool(rules and evaluate_dynamic_routes(rules, route))


def can_open_members_only_pages() -> bool:
	"""True for an active, living member who is not a visitor or contact, and for a Web Page editor."""
	if frappe.has_permission("Web Page", "write"):
		return True
	person = session_person()
	return bool(person) and is_directory_member(person)


@frappe.whitelist()
def get_list_data(doctype: str, **kwargs):
	"""Frappe's portal list API, without the members-only Web Pages the caller may not open.

	Frappe lists every published Web Page, with all its fields, to any signed-in user.
	"""
	if doctype == "Web Page" and not can_open_members_only_pages():
		kwargs["members_only"] = "0"
	return portal_list.get_list_data(doctype, **kwargs)


class MembersOnlyWebPage:
	"""Web Page extension: a members-only page stays out of the guest search index.

	Frappe's global search and Google indexing treat a page as public when ``is_website_published``
	is true, and the guest ``web_search`` API returns its text.
	"""

	def is_website_published(self):
		return super().is_website_published() and not self.get("members_only")

	def set_route(self):
		if self.published and not self.route:
			self.route = self.make_route()
		super().set_route()

	def onload(self):
		super().onload()
		self.get("__onload").published = self.published
