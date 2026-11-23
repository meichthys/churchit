# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the website palettes: one Website Theme for each, with its Color records.

The website and the member app now share one look, colored by the website's Website Theme
(church_website/palette.py). The Churchit theme of an older site, made with no colors, gets the
member app's own colors; a theme a church made or changed keeps its colors, and the site keeps the
theme it uses.

The look no longer comes from SCSS compiled into each theme. Migrate compiles only the theme in use
again, so every other theme compiled with this app's old SCSS is saved here, or picking it later
would bring back the old look over the new one.
"""

import frappe

from churchit.patches.after_install import create_website_theme

OLD_SCSS = "churchit/public/scss/website"


def execute():
	create_website_theme()

	for theme in frappe.get_all(
		"Website Theme", filters={"theme_scss": ["like", f"%{OLD_SCSS}%"]}, pluck="name"
	):
		frappe.get_doc("Website Theme", theme).save(ignore_permissions=True)
