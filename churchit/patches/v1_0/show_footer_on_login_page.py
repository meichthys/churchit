# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Show the website footer, with the church's name and links, on the login page.

Frappe's login page shows the logo in Navbar Settings and no name, so it did not look like the
church's site. Website Settings' Show Footer on Login adds the footer. A church that already set it
keeps its choice: Website Settings keeps a Version of each save.
"""

import frappe


def execute():
	if frappe.db.exists(
		"Version", {"ref_doctype": "Website Settings", "data": ("like", '%"show_footer_on_login"%')}
	):
		return
	frappe.db.set_single_value("Website Settings", "show_footer_on_login", 1)
