# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Scope the shipped website pages to the selected church on existing sites.

The pages are user-owned starter data, so this rewrites only the query filters
this app shipped and leaves every other edit in place: a church that restyled
its home page keeps the restyling and gains the scoping. A church that rewrote
one of these queries keeps its own, unscoped, and is named in the patch log.

The retired ``locations`` page is unpublished so ``www/locations.py`` can serve
the route, because a published Web Page is resolved ahead of a template page.
"""

from pathlib import Path

import frappe

SHIPPED_LOCATIONS = (Path(__file__).resolve().parent / "templates" / "locations_v1.html").read_text()

# Each shipped query as it was before scoping, and the same query scoped. Every
# pair stands alone, so a page is improved by whichever of them it still has.
SCOPED_QUERIES = (
	(
		'filters={"publish": 1, "start_date": [">=", frappe.utils.nowdate()]}',
		'filters=selected_church_filters(publish=1, start_date=[">=", frappe.utils.nowdate()])',
	),
	(
		'filters={"publish": 1, "status": "Active"}',
		'filters=selected_church_filters(publish=1, status="Active")',
	),
	('filters={"publish": 1}', "filters=selected_church_filters(publish=1)"),
	(
		'frappe.db.count("Ministry", {"publish": 1})',
		'frappe.db.count("Ministry", selected_church_filters(publish=1))',
	),
	(
		'frappe.db.count("Missionary", {"publish": 1})',
		'frappe.db.count("Missionary", selected_church_filters(publish=1))',
	),
	(
		'frappe.db.count("Sermon", {"publish": 1})',
		'frappe.db.count("Sermon", selected_church_filters(publish=1))',
	),
)

# Belief was global when this patch shipped, so the beliefs page had nothing to
# scope. It gained a church later; scope_beliefs_page_to_church picks it up.
PAGES = ("home", "sermons", "ministries", "missions")


def execute():
	for name in PAGES:
		scope_page(name)
	retire_locations_page()


def scope_page(name):
	"""Point one page's shipped queries at the selected church."""
	if not frappe.db.exists("Web Page", name):
		return

	doc = frappe.get_doc("Web Page", name)
	html = doc.main_section_html or ""
	for shipped, scoped in SCOPED_QUERIES:
		html = html.replace(shipped, scoped)
	if html == doc.main_section_html:
		return

	doc.main_section_html = html
	doc.save(ignore_permissions=True)


def retire_locations_page():
	"""Hand /locations to the app's own page, unless the church wrote its own."""
	page = frappe.db.get_value("Web Page", {"route": "locations", "published": 1}, "name")
	if not page:
		return

	doc = frappe.get_doc("Web Page", page)
	if doc.main_section_html != SHIPPED_LOCATIONS:
		print(f"Web Page {doc.name} still serves /locations; unpublish it to use the Locations page.")
		return

	doc.published = 0
	doc.save(ignore_permissions=True)
