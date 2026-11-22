# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member app's navigation: the site admin's Portal Settings menu, in the old portal home's sections.

The admin owns the menu rows (Desk > Portal Settings). A row for a page the app draws opens in the app at
/portal/<route>; any other row, such as one the admin added, stays a plain link.
"""

from frappe import _
from frappe.website.utils import get_portal_sidebar_items

from churchit.church_website.pages import get_hidden_pages, is_link_off, is_page_off
from churchit.church_website.portal_home import get_portal_home_sections

# The pages the app draws itself, by their old route.
APP_PAGES = frozenset(
	{
		"household",
		"personal-details",
		"preferences",
		"directory",
		"function-sign-up",
		"attendance",
		"ministry-team",
		"room-request",
		"groups",
		"group-leader",
		"group-files",
		"prayer-request",
		"community-prayer-requests",
		"care-request",
		"alms-request",
		"statements",
		"pledge",
		"bible",
		"memorize",
		"bulletins",
	}
)


def get_navigation(hidden: set[str]) -> list[dict]:
	"""The menu rows this member may see, in sections: [{title, links: [{page, title, description, app, href, target}]}]."""
	items = [item for item in get_portal_sidebar_items() if not is_link_off(item.get("route"), hidden)]
	return [
		{"title": section.title, "links": [get_link(row) for row in section.links]}
		for section in get_portal_home_sections(items)
	]


def get_link(row: dict) -> dict:
	"""One menu row as the app draws it."""
	route = (row.get("route") or "").strip()
	page = route.strip("/")
	in_app = page in APP_PAGES
	return {
		"page": page,
		"title": _(row.get("title") or ""),
		"description": row.get("description") or "",
		"app": in_app,
		"href": None if in_app else route if "://" in route else "/" + page,
		"target": row.get("target") or None,
	}


def get_site_links(hidden: set[str]) -> list[dict]:
	"""The website pages outside the portal menu that the app links to, less those this member must not see."""
	links = (
		("give", _("Give")),
		("register", _("Sign Up for an Event")),
		("calendar", _("Calendar")),
		("sermons", _("Sermons")),
	)
	return [
		{"page": page, "title": title, "href": "/" + page}
		for page, title in links
		if not is_page_off(page, hidden)
	]


# The website pages the app links to, which it also checks against the hidden pages.
SITE_PAGES = frozenset({"give", "register", "calendar", "sermons"})


def get_menu() -> dict:
	"""The navigation, the website links and the hidden pages, for the app's boot.

	Only the app's own pages and its website links go to the browser: the hidden set also holds the
	routes of the members-only Web Pages a visitor may not open, which the browser must not learn.
	"""
	hidden = get_hidden_pages()
	return {
		"navigation": get_navigation(hidden),
		"site_links": get_site_links(hidden),
		"hidden_pages": sorted(page for page in hidden if page in APP_PAGES or page in SITE_PAGES),
	}
