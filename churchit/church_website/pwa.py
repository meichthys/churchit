# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What makes the site installable as an app: the web app manifest and the head tags that point to it."""

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import escape_html
from frappe.website.page_renderers.base_renderer import BaseRenderer

from churchit.church_foundations.doctype.church.church import get_church
from churchit.church_scope import is_feature_enabled
from churchit.church_website.pages import SHIPPED_PAGES, get_switched_off_pages

MANIFEST_URL = "/manifest.json"
START_URL = "/app-start"
# The start_url before /app-start, which a manifest without an id names its app by. Keeping it
# keeps the apps members already installed as the same app.
APP_ID = "/portal"
PORTAL_URL = "/portal"
DESK_URL = "/desk"
ICON_DIR = "/assets/churchit/icons/pwa"
DEFAULT_NAME = "Churchit"
# Long-press (phone) or right-click (computer) menu of the app icon.
SHORTCUT_PAGES = ("calendar", "prayer-request", "give", "sermons")

# --bg-color in public/scss/website.scss. The browser chrome and the splash
# screen match the page behind the frosted navbar, not the brand accent.
THEME_COLOR = {"light": "#eef1fb", "dark": "#0b1020"}

ICONS = [
	{"src": f"{ICON_DIR}/icon-192.png", "sizes": "192x192", "type": "image/png"},
	{"src": f"{ICON_DIR}/icon-512.png", "sizes": "512x512", "type": "image/png"},
	{
		"src": f"{ICON_DIR}/icon-512-maskable.png",
		"sizes": "512x512",
		"type": "image/png",
		"purpose": "maskable",
	},
]


def get_manifest():
	name, short_name = app_names()
	return {
		"id": APP_ID,
		"name": name,
		"short_name": short_name,
		"description": _("{0} on your phone and computer.").format(name),
		"start_url": START_URL,
		"scope": "/",
		"display": "standalone",
		# A second launch brings the open window forward instead of opening another.
		"launch_handler": {"client_mode": ["focus-existing", "auto"]},
		"background_color": THEME_COLOR["light"],
		"theme_color": THEME_COLOR["light"],
		"categories": ["lifestyle", "social"],
		"icons": ICONS,
		"shortcuts": get_shortcuts(),
	}


def get_shortcuts():
	off_pages = get_switched_off_pages()
	return [
		{"name": _(SHIPPED_PAGES[route][0]), "url": f"/{route}"}
		for route in SHORTCUT_PAGES
		if route not in off_pages
	]


def head_tags():
	"""The tags every website page needs for the browser to offer an install.

	theme-color holds both palettes: theme_mode.js swaps content= with the
	light/dark switch, which a media query can't follow. The desk keeps Frappe's own.
	"""
	light, dark = THEME_COLOR["light"], THEME_COLOR["dark"]
	return (
		install_tags()
		+ f'<meta name="theme-color" content="{light}" data-light="{light}" data-dark="{dark}">'
	)


def install_tags():
	"""The tags that make a page installable, for the website head and the desk (through its boot).

	iOS ignores manifest icons and, before 15.4, the manifest name, so the
	apple tags carry those too. public/js/pwa.js names the app in its install
	card from application-name, and offers the install by itself only while the
	churchit-offer-install tag is there.
	"""
	name, short_name = (escape_html(value) for value in app_names())
	tags = (
		f'<link rel="manifest" href="{MANIFEST_URL}">'
		f'<link rel="apple-touch-icon" href="{ICON_DIR}/apple-touch-icon.png">'
		'<meta name="apple-mobile-web-app-capable" content="yes">'
		'<meta name="apple-mobile-web-app-status-bar-style" content="default">'
		f'<meta name="apple-mobile-web-app-title" content="{short_name}">'
		f'<meta name="application-name" content="{name}">'
	)
	if is_feature_enabled("offer_app_install"):
		tags += '<meta name="churchit-offer-install" content="1">'
	return tags


def extend_bootinfo(bootinfo):
	"""Give the desk the install tags, which public/js/pwa.js adds to its head."""
	bootinfo.pwa_install_tags = install_tags()


def app_names():
	"""(name, short_name) for the installed app, from the Church record.

	The abbreviation is the short name: home screens truncate anything much
	longer than a dozen characters.
	"""
	church = get_church()
	if not church:
		return DEFAULT_NAME, DEFAULT_NAME
	return church.church_name, church.abbreviation or church.church_name


class AppStartPage(BaseRenderer):
	"""/app-start, where the installed app opens: the desk for staff, the portal for members.

	A 302, because the browser must not keep an answer that depends on who signed in.
	"""

	def can_render(self):
		return self.path == START_URL.strip("/")

	def render(self):
		user = frappe.session.user
		if user == "Guest":
			frappe.flags.redirect_location = "/login?" + urlencode({"redirect-to": START_URL}, safe="/")
		elif frappe.db.get_value("User", user, "user_type") == "System User":
			frappe.flags.redirect_location = DESK_URL
		else:
			frappe.flags.redirect_location = PORTAL_URL
		raise frappe.Redirect(302)
