# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Hide the home page's sermon card, link and count on existing sites while the sermons page is off.

The home page is user-owned starter data. An edited page gets the fix too, but only the sermon
query and the sermon count change; the rest of the page stays as the church wrote it.
"""

import frappe

SERMONS_QUERY = "{%- set sermons = frappe.get_all("
SERMONS_ON = '{%- set sermons_on = "sermons" not in get_switched_off_pages() -%}\n'
QUERY_END = ") -%}"
QUERY_END_ON = ") if sermons_on else [] -%}"
COUNT = '), "label": _("Sermons online")}'
COUNT_ON = ') if sermons_on else 0, "label": _("Sermons online")}'


def execute():
	if not frappe.db.exists("Web Page", "home"):
		return

	doc = frappe.get_doc("Web Page", "home")
	html = doc.main_section_html or ""
	head, query, tail = html.partition(SERMONS_QUERY)
	arguments, end, rest = tail.partition(QUERY_END)
	if not query or not end or "sermons_on" in html:
		return

	# Only the end of the sermon query itself: another query on an edited page keeps its own.
	html = head + SERMONS_ON + query + arguments + QUERY_END_ON + rest
	doc.main_section_html = html.replace(COUNT, COUNT_ON, 1)
	doc.save(ignore_permissions=True)
