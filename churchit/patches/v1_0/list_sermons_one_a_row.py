# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the sermons page as a list: one sermon a row, the rest of a series under it.

The ``sermons`` Web Page is user-owned starter data, so only a page that still holds the template
this app shipped before is replaced, whatever its whitespace. A church that edited its page keeps it.
"""

from pathlib import Path

import frappe

from churchit.patches.after_install import read_template
from churchit.patches.v1_0.build_sermon_library import without_whitespace

SHIPPED_SERMONS = (Path(__file__).resolve().parent / "templates" / "sermons_v2.html").read_text()


def execute():
	if not frappe.db.exists("Web Page", "sermons"):
		return

	doc = frappe.get_doc("Web Page", "sermons")
	if without_whitespace(doc.main_section_html) != without_whitespace(SHIPPED_SERMONS):
		print("Web Page sermons was edited, so it keeps its own layout instead of the sermon list.")
		return

	doc.main_section_html = read_template("sermons.html")
	doc.save(ignore_permissions=True)
