# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What makes the site installable as an app: the web app manifest and the head tags that point to it."""

from frappe.utils import escape_html

from churchit.church_foundations.doctype.church.church import get_church

MANIFEST_URL = "/manifest.json"
START_URL = "/portal"
ICON_DIR = "/assets/churchit/icons/pwa"
DEFAULT_NAME = "Churchit"

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
		"name": name,
		"short_name": short_name,
		"start_url": START_URL,
		"scope": "/",
		"display": "standalone",
		"background_color": THEME_COLOR["light"],
		"theme_color": THEME_COLOR["light"],
		"icons": ICONS,
	}


def head_tags():
	"""The tags every website page needs for the browser to offer an install.

	iOS ignores manifest icons and, before 15.4, the manifest name, so the
	apple tags carry those too. theme-color holds both palettes: theme_mode.js
	swaps content= with the light/dark switch, which a media query can't follow.
	"""
	light, dark = THEME_COLOR["light"], THEME_COLOR["dark"]
	short_name = escape_html(app_names()[1])
	return (
		f'<link rel="manifest" href="{MANIFEST_URL}">'
		f'<link rel="apple-touch-icon" href="{ICON_DIR}/apple-touch-icon.png">'
		f'<meta name="theme-color" content="{light}" data-light="{light}" data-dark="{dark}">'
		'<meta name="apple-mobile-web-app-capable" content="yes">'
		'<meta name="apple-mobile-web-app-status-bar-style" content="default">'
		f'<meta name="apple-mobile-web-app-title" content="{short_name}">'
	)


def app_names():
	"""(name, short_name) for the installed app, from the Church record.

	The abbreviation is the short name: home screens truncate anything much
	longer than a dozen characters.
	"""
	church = get_church()
	if not church:
		return DEFAULT_NAME, DEFAULT_NAME
	return church.church_name, church.abbreviation or church.church_name
