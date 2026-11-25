# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Website context additions, wired through the ``update_website_context`` hook."""

import copy
from pathlib import Path
from urllib.parse import unquote

import frappe
from frappe import _
from frappe.website.utils import get_portal_sidebar_items

from churchit.church_foundations.doctype.church.church import get_church, selected_church_name
from churchit.church_scope import is_multi_church
from churchit.church_website import pwa
from churchit.church_website.footer import get_footer_church
from churchit.church_website.pages import (
	get_hidden_pages,
	get_members_only_routes,
	get_switched_off_pages,
	is_file_route,
	is_link_off,
	is_public_website_on,
)
from churchit.www.podcast import get_feed_url

PORTAL_URL = "/portal"
# The www page that holds the member app at /portal and every path under it.
MEMBER_APP_PAGE = "member_portal"
# The pages that draw a Leaflet map.
MAP_PAGES = ("missions", "find-a-group", "calendar")
THEME_MODE_SCRIPT = (
	"<script>" + (Path(__file__).parents[1] / "public/js/theme_mode.js").read_text() + "</script>"
)


def update_website_context(context):
	path = context.get("path")
	if is_file_route(path):
		# A file such as /sw.js has no menu, head or footer; the sitemap still drops hidden links.
		if path == "sitemap.xml":
			_hide_closed_links(context)
		return
	if path == MEMBER_APP_PAGE:
		# The member app (frontend/) draws its own menu and has no footer: it needs only the head,
		# with the browser chrome in the app's own paper colors.
		context["head_html"] = (context.get("head_html") or "") + pwa.head_tags(pwa.APP_THEME_COLOR)
		_add_theme_mode_script(context)
		return

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
	"""Keep signed-in visitors off the shared page cache once branches or members-only pages exist,
	or while the public website is off.

	Frappe caches a rendered page by path alone. A member's pages show their
	own church, and their menu links the members-only pages, so serving them the
	cached guest copy (or caching theirs for guests) would show the wrong church
	or links. An API call reads no page cache, and a file such as /sw.js is the same for every
	visitor or keeps itself out of the cache, so both skip the check.
	"""
	path = frappe.request.path
	if frappe.session.user == "Guest" or path.startswith("/api/") or is_file_route(path):
		return
	if is_multi_church() or get_members_only_routes() or not is_public_website_on():
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

	menu.insert(0, {"label": _("Member Portal"), "url": PORTAL_URL})


def _set_portal_sidebar(context):
	"""Fill a shown sidebar with the member portal menu, led by the member app, and make its links absolute.

	Frappe already falls back to the Portal Settings menu for www pages, but a
	web form fills its sidebar from a Website Sidebar record alone, so a form
	showed My Account and nothing else. Frappe also renders a route as typed,
	and "bible" seen from a form's /<route>/new is /<route>/bible. A page with
	its own Website Sidebar keeps that menu as it is.
	"""
	if not context.get("show_sidebar"):
		return
	items = [
		_with_absolute_route(item) for item in context.get("sidebar_items") or get_portal_sidebar_items()
	]
	own_sidebar = context.get("website_sidebar") or (context.get("web_form_doc") or {}).get("website_sidebar")
	if (
		not own_sidebar
		and frappe.session.user != "Guest"
		and all(item.get("route") != PORTAL_URL for item in items)
	):
		items.insert(0, frappe._dict(title=_("Member Portal"), route=PORTAL_URL))
	context["sidebar_items"] = items


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
	church that has set its own brand_html, or a logo in Banner Image, keeps it:
	the navbar shows Banner Image only while brand_html is empty.
	"""
	if context.get("brand_html") or context.get("banner_image"):
		return

	church = get_church()
	if church:
		context["brand_html"] = f"<span>{frappe.utils.escape_html(church.church_name)}</span>"


def _add_locations_menu(context):
	"""A Locations dropdown of the published churches, once there is more than one, beside Home.

	The dropdown marks the church the page shows. The body class lets website.css take Home off a
	narrower bar, where both do not fit on one row. The menu rows are Website Settings' cached rows,
	so this builds a new list.
	"""
	if not is_multi_church():
		return
	churches = frappe.get_all(
		"Church", filters={"publish": 1}, fields=["name", "church_name"], order_by="lft asc"
	)
	if len(churches) < 2:
		return
	path = frappe.local.request.path if getattr(frappe.local, "request", None) else "/"
	selected = selected_church_name()
	items = [
		frappe._dict(
			label=_("{0} (selected)").format(church.church_name)
			if church.name == selected
			else church.church_name,
			url=f"{path}?church={church.name}",
		)
		for church in churches
	]
	items.append(frappe._dict(label=_("All locations"), url="/locations"))
	context["top_bar_items"] = [
		*(context.get("top_bar_items") or []),
		frappe._dict(label=_("Locations"), right=1, child_items=items),
	]
	context["body_class"] = f"{context.get('body_class') or ''} has-locations-menu".strip()


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
