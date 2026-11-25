# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The theme picker of Website Settings: each Website Theme with the colors of its light and dark pages."""

import frappe
from frappe import _

from churchit.church_website.palette import PALETTES, STANDARD_THEME, get_theme_palette, make_tokens

# Frappe's own colors, which the Standard theme keeps (Espresso's tokens in each mode).
STANDARD_PREVIEW = {
	"light": {
		"paper": "#ffffff",
		"ink": "#0f0f0f",
		"muted": "#525252",
		"rule": "#e2e2e2",
		"accent": "#0d8ef8",
	},
	"dark": {
		"paper": "#171717",
		"ink": "#f3f3f3",
		"muted": "#afafaf",
		"rule": "#383838",
		"accent": "#61afef",
	},
}
# The tokens a preview shows, by the name the picker gives each.
PREVIEW_TOKENS = {
	"paper": "surface-base",
	"ink": "ink-gray-9",
	"muted": "ink-gray-6",
	"rule": "outline-gray-2",
	"accent": "accent",
}


@frappe.whitelist(methods=["GET"])
def get_website_theme_palettes() -> list[dict]:
	"""Each Website Theme with its light and dark colors, shipped palettes first. Reads only."""
	frappe.has_permission("Website Settings", throw=True)
	themes = frappe.get_all("Website Theme", pluck="name", order_by="name asc")
	shipped = [theme for theme in PALETTES if theme in themes]
	others = [theme for theme in themes if theme not in PALETTES and theme != STANDARD_THEME]
	return [
		{"name": theme, **preview}
		for theme in [*shipped, *others, STANDARD_THEME]
		if (preview := get_preview(theme))
	]


# The swatch row of the Website Settings form called this before the picker. Kept for one release
# (to 2027) for the copies of website_settings.js that browsers still hold; then remove it.
@frappe.whitelist(methods=["GET", "POST"])
def get_website_theme_palette(theme: str) -> list[dict]:
	"""The swatches of *theme*, as [{"label", "color"}, …]. Reads only."""
	frappe.has_permission("Website Settings", throw=True)
	light = (get_preview(theme) or {}).get("light") or {}
	labels = {"accent": _("Accent"), "paper": _("Background"), "ink": _("Text")}
	return [{"label": label, "color": light[key]} for key, label in labels.items() if key in light]


def get_preview(theme: str) -> dict | None:
	"""The preview colors of *theme* in each mode, or None when there is no such theme."""
	if theme == STANDARD_THEME:
		return STANDARD_PREVIEW
	colors = get_theme_palette(theme)
	if not colors:
		return None
	tokens = make_tokens(*colors)
	return {
		mode: {name: tokens[mode][token] for name, token in PREVIEW_TOKENS.items()}
		for mode in ("light", "dark")
	}
