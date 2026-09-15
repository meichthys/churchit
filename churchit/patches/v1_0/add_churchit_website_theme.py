# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Churchit website theme.

The look this app ships used to be plain CSS loaded on every page. It is now
the "Churchit" Website Theme, so a church can switch between it and frappe's
plain "Standard" theme in Website Settings. Sites still on Standard — the value
after_install used to set — move to Churchit so the site looks as it did. A
church that picked a theme of its own keeps it; frappe compiles this app's
styles into that theme too, as before.
"""

import frappe

from churchit.patches.after_install import WEBSITE_THEME, create_website_theme


def execute():
	create_website_theme()

	settings = frappe.get_doc("Website Settings")
	if settings.website_theme and settings.website_theme != "Standard":
		return

	settings.website_theme = WEBSITE_THEME
	settings.save(ignore_permissions=True)
