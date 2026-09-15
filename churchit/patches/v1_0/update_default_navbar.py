# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Bring the website navbar on existing sites in line with the shipped default.

The navbar is seeded by after_install, which only runs on a fresh install, so
existing sites keep whatever was current when they were created:

- Calendar is added, because /calendar is otherwise unreachable from the site.
- Locations is dropped: only one Church record is allowed, so the page repeats
  what About Us and the church record already say. The page stays published, so
  a church with more than one meeting place can link to it again.

Both steps only touch rows this app shipped, leaving a renamed or re-pointed
entry — and the rest of the menu — as the admin left it.
"""

import frappe

CALENDAR = {"label": "Calendar", "url": "/calendar"}
CALENDAR_ANCHOR = "/ministries"
LOCATIONS = {"label": "Locations", "url": "/locations"}


def execute():
	settings = frappe.get_doc("Website Settings")
	changed = _add_calendar(settings) | _remove_locations(settings)
	if not changed:
		return

	for position, row in enumerate(settings.top_bar_items, start=1):
		row.idx = position
	settings.save(ignore_permissions=True)


def _add_calendar(settings) -> bool:
	if any(_route(row) == CALENDAR["url"] for row in settings.top_bar_items):
		return False

	item = settings.append("top_bar_items", {**CALENDAR, "right": 1})
	anchor = next((i for i, row in enumerate(settings.top_bar_items) if _route(row) == CALENDAR_ANCHOR), None)
	if anchor is not None:
		settings.top_bar_items.remove(item)
		settings.top_bar_items.insert(anchor + 1, item)
	return True


def _remove_locations(settings) -> bool:
	shipped = [
		row
		for row in settings.top_bar_items
		if row.label == LOCATIONS["label"] and _route(row) == LOCATIONS["url"]
	]
	for row in shipped:
		settings.top_bar_items.remove(row)
	return bool(shipped)


def _route(row) -> str:
	return (row.url or "").rstrip("/")
