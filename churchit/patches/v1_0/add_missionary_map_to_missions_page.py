"""Add the missionary map to the public Missions web page on existing sites.

The `missions` Web Page is user-owned starter data (see `after_install`), so
this only prepends the map container — it never touches or replaces whatever
content is already there, published or user-edited.
"""

import frappe

MAP_MARKUP = '<div class="missions-map-card">\n    <div id="missions-map" class="missions-map"></div>\n</div>\n\n'


def execute():
	if not frappe.db.exists("Web Page", "missions"):
		return

	doc = frappe.get_doc("Web Page", "missions")
	if "missions-map" in (doc.main_section_html or ""):
		return

	doc.main_section_html = MAP_MARKUP + (doc.main_section_html or "")
	doc.save(ignore_permissions=True)
