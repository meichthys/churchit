# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Leave link-only Functions out of the home page's upcoming events on existing sites.

The home page is user-owned starter data, so this rewrites only the query this
app shipped. A church that rewrote it keeps its own.
"""

import frappe

SHIPPED = 'filters=selected_church_filters(publish=1, start_date=[">=", frappe.utils.nowdate()])'
LINK_ONLY_HIDDEN = (
	'filters=selected_church_filters(publish=1, is_link_only=0, start_date=[">=", frappe.utils.nowdate()])'
)


def execute():
	if not frappe.db.exists("Web Page", "home"):
		return

	doc = frappe.get_doc("Web Page", "home")
	html = (doc.main_section_html or "").replace(SHIPPED, LINK_ONLY_HIDDEN)
	if html == doc.main_section_html:
		return

	doc.main_section_html = html
	doc.save(ignore_permissions=True)
