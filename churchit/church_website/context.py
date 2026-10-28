# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Website context additions, wired through the ``update_website_context`` hook."""

import copy
from pathlib import Path
from urllib.parse import unquote

import frappe
from frappe import _
from frappe.website.utils import get_portal_sidebar_items

from churchit.church_foundations.doctype.church.church import get_church
from churchit.church_scope import is_multi_church
from churchit.church_website import pwa
from churchit.church_website.footer import get_footer_church
from churchit.church_website.pages import (
	get_hidden_pages,
	get_members_only_routes,
	get_switched_off_pages,
	is_link_off,
)
from churchit.www.podcast import get_feed_url

PORTAL_URL = "/portal"
# The pages that draw a Leaflet map.
MAP_PAGES = ("missions", "find-a-group", "calendar")
THEME_MODE_SCRIPT = (
	"<script>" + (Path(__file__).parents[1] / "public/js/theme_mode.js").read_text() + "</script>"
)


def update_website_context(context):
	_add_portal_menu_item(context)
	_set_portal_sidebar(context)
	_set_brand_html(context)
	_add_locations_menu(context)
	context["footer_church"] = get_footer_church()
	_add_pwa_head_tags(context)
	_add_theme_mode_script(context)
	_add_leaflet(context)
	_add_podcast_link(context)
	_hide_closed_links(context)


def before_request():
	"""Keep signed-in visitors off the shared page cache once branches or members-only pages exist.

	Frappe caches a rendered page by path alone. A member's pages show their
	own church, and their menu links the members-only pages, so serving them the
	cached guest copy (or caching theirs for guests) would show the wrong church
	or links. An API call reads no page cache, so it skips the check.
	"""
	if frappe.session.user == "Guest" or frappe.request.path.startswith("/api/"):
		return
	if is_multi_church() or get_members_only_routes():
		frappe.local.no_cache = 1


def _add_portal_menu_item(context):
	"""Put the member portal in the top-right user menu.

	Frappe builds that menu with only My Account and Log out, and its own Portal
	link on /me is shown to Website Users alone, so staff, who are System Users,
	had no route into the portal at all.
	"""
	if frappe.session.user == "Guest":
		return

	menu = context.get("post_login")
	if not isinstance(menu, list) or any(item.get("url") == PORTAL_URL for item in menu):
		return

	menu.insert(0, {"label": _("Portal"), "url": PORTAL_URL})


def _set_portal_sidebar(context):
	"""Fill a shown sidebar with the member portal menu and make its links absolute.

	Frappe already falls back to the Portal Settings menu for www pages, but a
	web form fills its sidebar from a Website Sidebar record alone, so the
	portal's forms showed My Account and nothing else. Frappe also renders a
	route as typed, and "bible" seen from /prayer-request/new is
	/prayer-request/bible.
	"""
	if not context.get("show_sidebar"):
		return
	items = context.get("sidebar_items") or get_portal_sidebar_items()
	context["sidebar_items"] = [_with_absolute_route(item) for item in items]


def _with_absolute_route(item):
	route = item.get("route")
	if not route or route.startswith("/") or "://" in route:
		return item
	return frappe._dict(item, route=f"/{route}")


def _set_brand_html(context):
	"""Show the church's name in the navbar brand instead of Frappe's "Home" fallback.

	Website Settings.brand_html is the field the navbar actually checks first;
	leaving it blank lets this fill in the current church name on every request
	instead of freezing a copy that would drift once the church is renamed. A
	church that has set its own brand_html (a logo, say) keeps it untouched.
	"""
	if context.get("brand_html"):
		return

	church = get_church()
	if church:
		context["brand_html"] = f"<span>{frappe.utils.escape_html(church.church_name)}</span>"


def _add_locations_menu(context):
	"""A Locations dropdown of the published churches, once there is more than one."""
	if not is_multi_church():
		return
	churches = frappe.get_all(
		"Church", filters={"publish": 1}, fields=["name", "church_name"], order_by="lft asc"
	)
	if len(churches) < 2:
		return
	path = frappe.local.request.path if getattr(frappe.local, "request", None) else "/"
	items = [
		frappe._dict(label=church.church_name, url=f"{path}?church={church.name}") for church in churches
	]
	items.append(frappe._dict(label=_("All locations"), url="/locations"))
	context.setdefault("top_bar_items", []).append(
		frappe._dict(label=_("Locations"), right=1, child_items=items)
	)


def _add_pwa_head_tags(context):
	"""Make every page installable. Anything the church put in head_html stays in front."""
	context["head_html"] = (context.get("head_html") or "") + pwa.head_tags()


def _add_theme_mode_script(context):
	"""Apply the visitor's light/dark choice before the page first paints.

	Website Settings.head_html is the first thing rendered in <head>, ahead of
	the stylesheets; web_include_js only runs at the end of the body, which
	would flash the light look on every load. Runs after the PWA tags so the
	script finds the theme-color meta it keeps in step with the switch.
	"""
	context["head_html"] = context["head_html"] + THEME_MODE_SCRIPT


def _add_leaflet(context):
	"""Load Leaflet on the pages with a map. The website bundle has no `frappe.require`.

	Frappe hands every page the cached hook lists, so this assigns new lists.
	"""
	if getattr(frappe.local, "path", None) not in MAP_PAGES or "leaflet.bundle.js" in context.web_include_js:
		return
	context.web_include_js = ["leaflet.bundle.js", *context.web_include_js]
	context.web_include_css = ["leaflet.bundle.css", *context.web_include_css]


def _add_podcast_link(context):
	"""Point feed readers at the podcast from the sermons page."""
	if getattr(frappe.local, "path", None) != "sermons" or "podcast.xml" in get_switched_off_pages():
		return
	church = get_church()
	href = get_feed_url(church and church.name)
	title = frappe.utils.escape_html(_("Sermon Podcast"))
	context["head_html"] += f'<link rel="alternate" type="application/rss+xml" title="{title}" href="{href}">'


def _hide_closed_links(context):
	"""Drop navbar, footer, sidebar and sitemap links to the pages this visitor must not see.

	The menu rows are Website Settings' cached rows, so this builds new lists and copies a row
	before it changes the row's children.
	"""
	off_pages = get_hidden_pages()
	if not off_pages:
		return

	for key in ("top_bar_items", "footer_items"):
		if context.get(key):
			context[key] = _menu_without(context[key], off_pages)
	if context.get("sidebar_items"):
		context["sidebar_items"] = [
			item for item in context["sidebar_items"] if not is_link_off(item.get("route"), off_pages)
		]
	# Frappe's sitemap has no hook of its own; each loc is a full, quoted URL.
	if context.get("path") == "sitemap.xml" and context.get("links"):
		context["links"] = [
			link for link in context["links"] if not is_link_off(unquote(link["loc"]), off_pages)
		]


def _menu_without(items, off_pages):
	kept = []
	for item in items:
		if is_link_off(item.get("url"), off_pages):
			continue
		children = item.get("child_items") or []
		kept_children = [child for child in children if not is_link_off(child.get("url"), off_pages)]
		if len(kept_children) != len(children):
			if not kept_children and not item.get("url"):
				continue
			item = copy.copy(item)
			item.child_items = kept_children
		kept.append(item)
	return kept
