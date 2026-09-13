# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Refresh the home page's built-in look on existing sites.

The `home` Web Page is user-owned starter data (see `after_install`), so this
only replaces content that still matches the single-card layout this app
originally shipped. A church that has edited its home page keeps its edits.
"""

from pathlib import Path

import frappe

from churchit.patches.after_install import read_template

SHIPPED_DEFAULT = (Path(__file__).resolve().parent / "templates" / "home_v1.html").read_text()


def execute():
	if not frappe.db.exists("Web Page", "home"):
		return

	doc = frappe.get_doc("Web Page", "home")
	if doc.main_section_html != SHIPPED_DEFAULT:
		return

	doc.main_section_html = read_template("home.html")
	doc.save(ignore_permissions=True)
