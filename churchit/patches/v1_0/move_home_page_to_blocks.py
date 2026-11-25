# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Build the shipped home page from the church's Web Template blocks on existing sites.

The home page welcomes a visitor with when and where the church meets, then shows what is coming up,
the recent sermons with the podcast, the announcements, the ministries, the next steps and how to
visit (church_website/blocks.py). A church moves, retitles or hides each block on the Web Page.

The page is user-owned starter data: it changes only while it is still the page this app shipped
(templates/home.html), so a home page the church rewrote stays as it is. The page keeps that HTML,
which the Content Type HTML shows again.
"""

import frappe

from churchit.church_website.blocks import set_home_blocks
from churchit.patches.after_install import read_template


def execute():
	page = frappe.db.get_value("Web Page", "home", ["main_section_html", "content_type"], as_dict=True)
	if not page or page.content_type != "HTML" or page.main_section_html != read_template("home.html"):
		return

	home = frappe.get_doc("Web Page", "home")
	set_home_blocks(home)
	home.save(ignore_permissions=True)
