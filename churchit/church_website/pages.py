# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Page renderers that turn shipped pages off and keep members-only Web Pages from guests."""

from urllib.parse import urlencode, urlsplit

import frappe
from frappe import _
from frappe.utils import cint, get_url
from frappe.website.page_renderers.base_renderer import BaseRenderer
from frappe.website.page_renderers.not_found_page import NotFoundPage
from frappe.website.router import evaluate_dynamic_routes
from frappe.website.utils import clear_cache
from frappe.www import list as portal_list
from werkzeug.routing import Rule

from churchit.church_scope import session_person
from churchit.church_website.menu import get_route
from churchit.www.directory import is_directory_member

# route: (label, the Church Features field whose module owns the page, or None)
SHIPPED_PAGES: dict[str, tuple[str, str | None]] = {
	"about": ("About", None),
	"contact": ("Contact", None),
	"beliefs": ("Beliefs", None),
	"locations": ("Locations", None),
	"form": ("Forms", None),
	"live": ("Watch Live", None),
	"directory": ("Member Directory", "enable_people"),
	"household": ("My Household", "enable_people"),
	"find-a-group": ("Find a Group", "enable_people"),
	"group-leader": ("Lead a Group", "enable_people"),
	"groups": ("Groups", "enable_people"),
	"group-files": ("Group Files", "enable_people"),
	"personal-details": ("Personal Details", "enable_people"),
	"update-your-details": ("Update Your Details", "enable_people"),
	"connection-card": ("Connection Card", "enable_people"),
	"care-request": ("Care Request", "enable_people"),
	"ministries": ("Ministries", "enable_ministries"),
	"calendar": ("Calendar", "enable_ministries"),
	"register": ("Register", "enable_ministries"),
	"function-sign-up": ("Function Sign-Up", "enable_ministries"),
	"attendance": ("Attendance", "enable_ministries"),
	"check-in-kiosk": ("Check In", "enable_ministries"),
	"ministry-team": ("Ministry Team", "enable_ministries"),
	"ministry-team-response": ("Ministry Team Request", "enable_ministries"),
	"prayer-request": ("Prayer Request", "enable_prayers"),
	"prayer-request-anonymous": ("Prayer Request (Anonymous)", "enable_prayers"),
	"community-prayer-requests": ("Community Prayer Requests", "enable_prayers"),
	"sermons": ("Sermons", "enable_study"),
	"sermon": ("Sermon", "enable_study"),
	"podcast.xml": ("Podcast", "enable_study"),
	"sermon_presentation": ("Sermon Presentation", "enable_study"),
	"bible": ("Bible", "enable_study"),
	"memorize": ("Bible Memory", "enable_study"),
	"bulletins": ("Bulletins", "enable_communications"),
	"announcements": ("Announcements", "enable_communications"),
	"missions": ("Missions", "enable_missions"),
	"room-request": ("Room Request", "enable_operations"),
	"give": ("Give", "enable_finances"),
	"statements": ("Giving Statements", "enable_finances"),
	"pledge": ("Pledge", "enable_finances"),
	"alms-request": ("Alms Request", "enable_finances"),
}


class SwitchedOffPage(BaseRenderer):
	"""A 404 for a shipped page that is switched off, or whose module is off."""

	def can_render(self):
		off_pages = get_switched_off_pages()
		if not off_pages:
			return False

		# A route rule hands over its endpoint ("sermon"), not the path ("sermon/<name>"). Read the
		# path from the request: only Frappe's own resolver sets frappe.local.path, Builder's does not.
		request = getattr(frappe.local, "request", None)
		if is_page_off(self.path, off_pages) or (request and is_page_off(request.path, off_pages)):
			return True

		# Frappe finds a Web Page by route with a case and accent insensitive lookup ("Sérmons").
		route = frappe.db.get_value("Web Page", {"route": self.path, "published": 1}, "route")
		return is_page_off(route, off_pages)

	def render(self):
		return NotFoundPage(self.path).render()


def get_switched_off_pages() -> set[str]:
	"""The shipped pages that are off, by their own switch or because their module is off."""
	features = frappe.get_cached_doc("Church Features")
	# Before migrate adds the table, no page has its own switch.
	switched_off = {row.route for row in features.get("website_pages") or [] if not cint(row.enabled)}
	return {
		route
		for route, (_label, module_field) in SHIPPED_PAGES.items()
		if route in switched_off or (module_field and not cint(features.get(module_field)))
	}


def is_page_off(route: str | None, off_pages: set[str]) -> bool:
	"""Whether *route* is a switched-off page or a path under one."""
	route = (route or "").strip("/").lower()
	return any(route == page or route.startswith(page + "/") for page in off_pages)


def is_link_off(url: str | None, off_pages: set[str]) -> bool:
	"""Whether a menu or sidebar link points at one of *off_pages*.

	A sidebar route may lack its "/", and a menu link may be a full URL to this site.
	"""
	parts = urlsplit(url or "")
	if parts.netloc == urlsplit(get_url()).netloc:
		url = parts.path
	if url and not url.startswith("/"):
		url = "/" + url
	return is_page_off(get_route(url), off_pages)


def sync_page_switches() -> bool:
	"""Give Church Features one row per shipped page, keeping each row's setting. Safe to run again.

	Returns whether it saved, and so applied, Church Features.
	"""
	features = frappe.get_single("Church Features")
	enabled = {row.route: cint(row.enabled) for row in features.website_pages}
	rows = [
		{"route": route, "label": label, "enabled": enabled.get(route, 1)}
		for route, (label, _module_field) in SHIPPED_PAGES.items()
	]
	current = [
		{"route": row.route, "label": row.label, "enabled": cint(row.enabled)}
		for row in features.website_pages
	]
	if current == rows:
		return False

	features.set("website_pages", rows)
	features.save(ignore_permissions=True)
	return True


class SwitchedOffWebForm:
	"""Web Form extension: Frappe's web form APIs refuse a form whose page is switched off.

	They check only ``published``, which the switch leaves alone.
	"""

	def raise_if_unpublished(self):
		super().raise_if_unpublished()
		if is_page_off(self.route, get_switched_off_pages()):
			frappe.throw(_("Not permitted"), frappe.PermissionError)


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


def get_members_only_routes() -> set[str]:
	"""The routes of the published members-only Web Pages, in lower case.

	A dynamic route counts from its fixed start, so "members/<name>" hides /members and every link under it.
	"""
	# Before migrate adds the field, no page is members-only.
	if not frappe.get_meta("Web Page").has_field("members_only"):
		return set()
	routes = frappe.get_all("Web Page", filters={"published": 1, "members_only": 1}, pluck="route")
	return {route.split("<")[0].strip("/").lower() for route in routes if route} - {""}


def get_hidden_pages() -> set[str]:
	"""The pages whose links this visitor must not see: switched-off pages, and members-only pages they cannot open."""
	hidden = get_switched_off_pages()
	members_only = get_members_only_routes()
	if members_only and not can_open_members_only_pages():
		hidden |= members_only
	return hidden


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

	def on_update(self):
		super().on_update()
		# Every cached page holds the menu, and Frappe clears only this page's own route.
		if self.has_value_changed("members_only"):
			clear_cache()
			frappe.db.after_commit.add(clear_cache)

	def onload(self):
		super().onload()
		self.get("__onload").published = self.published
