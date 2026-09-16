# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Swatch colors that sum up a Website Theme, read from its compiled stylesheet."""

import re

import frappe

BRAND_TOKENS = {"--ch-brand": "Brand", "--ch-brand-2": "Accent", "--ch-brand-3": "Accent"}
FALLBACK_BRAND_TOKENS = {"--primary": "Primary"}
SURFACE_TOKENS = {"--bg-color": "Background", "--text-color": "Text"}

ROOT_BLOCK = re.compile(r":root(?:\s*,\s*\[data-theme=\"?light\"?\])?\s*\{([^}]*)\}")
DECLARATION = re.compile(r"(--[\w-]+)\s*:\s*([^;]+)")
VARIABLE = re.compile(r"var\((--[\w-]+)\)")
DARK_MEDIA = re.compile(r"@media[^{]*prefers-color-scheme\s*:\s*dark[^{]*\{")


@frappe.whitelist()
def get_website_theme_palette(theme):
	"""Return ``[{"label", "color"}, …]`` for the swatches shown beside a theme picker."""
	frappe.has_permission("Website Settings", throw=True)
	tokens = get_root_tokens(read_stylesheet(theme))
	swatches = {**BRAND_TOKENS} if "--ch-brand" in tokens else {**FALLBACK_BRAND_TOKENS}
	swatches.update(SURFACE_TOKENS)
	return [
		{"label": label, "color": color}
		for token, label in swatches.items()
		if (color := resolve_color(tokens, token))
	]


def read_stylesheet(theme):
	"""The stylesheet frappe links for *theme*: the Standard theme uses the
	website bundle, every other theme its own compiled file under public files."""
	if theme == "Standard":
		url = frappe.utils.get_assets_json()["website.bundle.css"]
	else:
		url = frappe.get_cached_value("Website Theme", theme, "theme_url")
	return frappe.read_file(stylesheet_path(url)) if url else ""


def stylesheet_path(url):
	if url.startswith("/assets/"):
		app, _, rest = url.removeprefix("/assets/").partition("/")
		return frappe.get_app_path(app, "public", rest)
	return frappe.get_site_path("public", url.removeprefix("/"))


def get_root_tokens(css):
	"""Custom properties declared on ``:root``, later blocks winning like in CSS."""
	tokens = {}
	for block in ROOT_BLOCK.finditer(without_dark_media(css)):
		tokens.update(DECLARATION.findall(block.group(1)))
	return tokens


def without_dark_media(css):
	"""Drop ``@media (prefers-color-scheme: dark)`` blocks; their ``:root``
	tokens would otherwise shadow the light palette."""
	while match := DARK_MEDIA.search(css):
		css = css[: match.start()] + css[block_end(css, match.end()) :]
	return css


def block_end(css, start):
	depth = 1
	for index in range(start, len(css)):
		depth += {"{": 1, "}": -1}.get(css[index], 0)
		if depth == 0:
			return index + 1
	return len(css)


def resolve_color(tokens, token, depth=0):
	"""Follow ``var(--other)`` chains to a literal value; None when the token is
	missing, or is something more than a plain color, such as a gradient."""
	value = tokens.get(token, "").strip()
	if not value or depth > 10:
		return None
	reference = VARIABLE.fullmatch(value)
	if reference:
		return resolve_color(tokens, reference.group(1), depth + 1)
	return None if "(" in value and not value.startswith(("rgb", "hsl")) else value
