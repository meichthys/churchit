# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The colors of the website and the member app, worked out from the website's Website Theme.

A palette is three colors of a Website Theme: the Background Color is the paper, the Text Color the ink
and the Primary Color the accent. They become the Espresso tokens (--surface-*, --ink-*, --outline-*)
that Frappe's website and frappe-ui share, for the light and the dark mode, so one record colors both
the website and the member app (frontend/). Each token keeps the lightness of its step in the member
app's "Order of Service" look, so every palette reads as well as that look does. The theme sets only
the hue and a little chroma, blending from the paper's tint on light steps to the ink's on dark ones.

The accent marks only "now" and "do this" (today's date, an instruction, a line a live update changed),
so any brand color has to pass as text on the paper in both modes. Its hue is kept and its OKLCH
lightness forced into a band, with chroma capped so no color shouts.

The values are hex colors, which every browser reads, and the style uses selectors that outrank
Espresso's and frappe-ui's own token blocks, which load after it. The Standard theme has no palette:
it keeps Frappe's own colors.
"""

import math
import re
from functools import lru_cache

import frappe
from frappe.website.utils import clear_website_cache

HEX_COLOR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
STANDARD_THEME = "Standard"

# (paper, ink, accent) of each shipped Website Theme. Churchit is the member app's own look: warm
# paper, lamp-black ink and rubric red, the red of the instructions in a printed order of service.
PALETTES = {
	"Churchit": ("#fcfaf5", "#13100c", "#9b2f22"),
	"Harbor": ("#f6fbfe", "#09111c", "#1f4e8c"),
	"Meadow": ("#f5fdf1", "#08140c", "#2e6b3f"),
	"Indigo": ("#f9fafe", "#0d0f1d", "#4338ca"),
	"Vesper": ("#fff8fe", "#160d18", "#7b2d6b"),
	"Slate": ("#f7fbfc", "#0d1114", "#2b6c7a"),
}
DEFAULT_PALETTE = PALETTES["Churchit"]
# A palette's three colors: the Website Theme field that holds each, and the word its Color record ends in.
THEME_COLOR_FIELDS = ("background_color", "text_color", "primary_color")
COLOR_ROLES = ("Paper", "Ink", "Accent")

# (lowest lightness, highest lightness, highest chroma) of the accent on the light paper and on the dark page.
LIGHT_BAND = (0.40, 0.50, 0.16)
DARK_BAND = (0.74, 0.82, 0.13)
# The most chroma a paper or ink may bring, so a strong color tints the page and never paints it.
MAX_TINT_CHROMA = 0.03
# Below this chroma a color is gray and its hue means nothing.
GRAY_CHROMA = 0.002

# token: (OKLCH lightness, share of the ink's tint from 0 to 1, chroma scale). The member app's look,
# frappe-ui's own steps retuned (frontend/src/style.css keeps the same values as its fallback).
LIGHT_LADDER = {
	"surface-base": (0.985, 0, 0.7),
	"surface-sidebar": (0.966, 0, 0.9),
	"surface-elevation-1": (0.994, 0, 0.4),
	"surface-elevation-2": (0.994, 0, 0.4),
	"surface-elevation-3": (0.998, 0, 0.2),
	"surface-gray-1": (0.972, 0, 0.8),
	"surface-gray-2": (0.957, 0, 0.9),
	"surface-gray-3": (0.94, 0, 1),
	"surface-gray-4": (0.908, 0, 1),
	"surface-gray-5": (0.83, 0, 1),
	"surface-gray-6": (0.683, 1 / 3, 1),
	"surface-gray-7": (0.586, 1 / 3, 1),
	"surface-gray-8": (0.439, 2 / 3, 1),
	"surface-gray-9": (0.341, 2 / 3, 1),
	"surface-gray-10": (0.215, 1, 1),
	"ink-base": (0.985, 0, 0.7),
	"ink-gray-1": (0.94, 0, 0.8),
	"ink-gray-2": (0.908, 0, 0.8),
	"ink-gray-3": (0.83, 0, 0.8),
	"ink-gray-4": (0.66, 1 / 3, 1),
	"ink-gray-5": (0.535, 1 / 3, 1),
	"ink-gray-6": (0.439, 2 / 3, 1),
	"ink-gray-7": (0.341, 2 / 3, 1),
	"ink-gray-8": (0.215, 1, 1),
	"ink-gray-9": (0.175, 1, 1),
	"outline-gray-1": (0.915, 0, 1),
	"outline-gray-2": (0.88, 0, 1),
	"outline-gray-3": (0.83, 0, 1),
	"outline-gray-4": (0.683, 1 / 3, 1),
	"outline-gray-5": (0.586, 1 / 3, 1),
	"outline-gray-6": (0.439, 2 / 3, 1),
	"outline-gray-7": (0.341, 2 / 3, 1),
	"outline-gray-8": (0.215, 1, 1),
	"outline-gray-9": (0.175, 1, 1),
	"outline-elevation-1": (0.915, 0, 1),
	"outline-elevation-2": (0.915, 0, 1),
}
# In the dark mode the page takes the ink's tint and the text the paper's.
DARK_LADDER = {
	"surface-base": (0.205, 1, 0.6),
	"surface-sidebar": (0.185, 1, 0.6),
	"surface-elevation-1": (0.239, 1, 0.6),
	"surface-elevation-2": (0.26, 1, 0.6),
	"surface-elevation-3": (0.32, 1, 0.6),
	"surface-gray-1": (0.239, 1, 0.6),
	"surface-gray-2": (0.281, 1, 0.6),
	"surface-gray-3": (0.341, 1, 0.6),
	"surface-gray-4": (0.379, 1, 0.6),
	"surface-gray-5": (0.457, 1, 0.6),
	"surface-gray-6": (0.58, 2 / 3, 0.6),
	"surface-gray-7": (0.683, 2 / 3, 0.7),
	"surface-gray-8": (0.754, 1 / 3, 0.8),
	"surface-gray-9": (0.885, 0, 0.9),
	"surface-gray-10": (0.95, 0, 1),
	"ink-base": (0.205, 1, 0.6),
	"ink-gray-1": (0.26, 1, 0.6),
	"ink-gray-2": (0.341, 1, 0.6),
	"ink-gray-3": (0.42, 1, 0.6),
	"ink-gray-4": (0.58, 2 / 3, 0.7),
	"ink-gray-5": (0.645, 2 / 3, 0.8),
	"ink-gray-6": (0.72, 1 / 3, 0.8),
	"ink-gray-7": (0.79, 1 / 3, 0.9),
	"ink-gray-8": (0.885, 0, 1),
	"ink-gray-9": (0.95, 0, 1),
	"outline-gray-1": (0.3, 1, 0.6),
	"outline-gray-2": (0.36, 1, 0.6),
	"outline-gray-3": (0.4, 1, 0.6),
	"outline-gray-4": (0.457, 1, 0.6),
	"outline-gray-5": (0.58, 2 / 3, 0.7),
	"outline-gray-6": (0.683, 1 / 3, 0.8),
	"outline-gray-7": (0.94, 0, 1),
	"outline-gray-8": (0.96, 0, 1),
	"outline-gray-9": (0.975, 0, 1),
	"outline-elevation-1": (0.3, 1, 0.6),
	"outline-elevation-2": (0.36, 1, 0.6),
}


def get_website_palette() -> tuple[str, str, str] | None:
	"""The (paper, ink, accent) of the website's theme, or None while the site uses the Standard theme."""
	theme = get_previewed_theme() or frappe.get_website_settings("website_theme")
	return get_theme_palette(theme) if theme and theme != STANDARD_THEME else None


def get_previewed_theme() -> str | None:
	"""The theme that someone who may change Website Settings asked to see with ?theme_preview=<theme>.

	The query string keeps the page out of Frappe's page cache, so nobody else sees the preview."""
	theme = frappe.local.form_dict.get("theme_preview") if getattr(frappe.local, "form_dict", None) else None
	if isinstance(theme, str) and theme and frappe.has_permission("Website Settings", "write"):
		return theme
	return None


def get_theme_palette(theme: str) -> tuple[str, str, str] | None:
	"""The (paper, ink, accent) hex colors of *theme*, a color it leaves empty taken from the default,
	or None when there is no such theme (Frappe then shows the Standard theme too)."""
	links = frappe.get_cached_value("Website Theme", theme, list(THEME_COLOR_FIELDS))
	if not links:
		return None
	paper, ink, accent = (
		get_color(link) or default for link, default in zip(links, DEFAULT_PALETTE, strict=True)
	)
	return paper, ink, accent


def get_color(color: str | None) -> str | None:
	"""The hex value of a Color record, when it is one."""
	value = color and (frappe.get_cached_value("Color", color, "color") or "").strip()
	return value if value and HEX_COLOR.fullmatch(value) else None


def get_palette_style() -> str:
	"""The <style> that puts the website theme's palette on a page, or "" for the Standard theme."""
	colors = get_website_palette()
	return make_style(*colors) if colors else ""


def get_theme_color() -> dict[str, str] | None:
	"""The paper of the website theme in each mode, for the browser's chrome, or None for Standard."""
	colors = get_website_palette()
	if not colors:
		return None
	tokens = make_tokens(*colors)
	return {mode: tokens[mode]["surface-base"] for mode in ("light", "dark")}


def get_accent() -> dict[str, str]:
	"""The accent of the website theme in each mode; the Standard theme has the member app's own."""
	tokens = make_tokens(*(get_website_palette() or DEFAULT_PALETTE))
	return {mode: tokens[mode]["accent"] for mode in ("light", "dark")}


def clear_pages_on_color_change(doc, method: str | None = None) -> None:
	"""doc_events hook: when a Color of the website's theme changes, cached pages drop their palette."""
	theme = frappe.get_website_settings("website_theme")
	if theme and doc.name in (frappe.db.get_value("Website Theme", theme, list(THEME_COLOR_FIELDS)) or ()):
		clear_website_cache()


@lru_cache(maxsize=32)
def make_style(paper: str, ink: str, accent: str) -> str:
	"""A <style> with the palette's tokens for the light and the dark mode."""
	tokens = make_tokens(paper, ink, accent)
	light = ";".join(f"--{token}:{value}" for token, value in tokens["light"].items())
	dark = ";".join(f"--{token}:{value}" for token, value in tokens["dark"].items())
	return f'<style id="churchit-palette">html:root{{{light}}}html[data-theme="dark"]{{{dark}}}</style>'


@lru_cache(maxsize=32)
def make_tokens(paper: str, ink: str, accent: str) -> dict[str, dict[str, str]]:
	"""Every token of the palette, as {"light": {token: hex}, "dark": {token: hex}}. Shared: do not change it."""
	paper_tint, ink_tint = get_tint(paper, LIGHT_LADDER["surface-base"][2]), get_tint(ink, 1)
	paper_tint, ink_tint = same_hue_when_gray(paper_tint, ink_tint)
	return {
		"light": {
			**{token: blend(step, paper_tint, ink_tint) for token, step in LIGHT_LADDER.items()},
			"accent": clamp(accent, *LIGHT_BAND),
		},
		"dark": {
			**{token: blend(step, paper_tint, ink_tint) for token, step in DARK_LADDER.items()},
			"accent": clamp(accent, *DARK_BAND),
		},
	}


def get_tint(color: str, chroma_scale: float) -> tuple[float, float]:
	"""The (chroma, hue) that *color* gives the steps it tints, its chroma capped."""
	_lightness, chroma, hue = to_oklch(color)
	return min(chroma / chroma_scale, MAX_TINT_CHROMA), hue


def same_hue_when_gray(paper_tint: tuple, ink_tint: tuple) -> tuple[tuple, tuple]:
	"""A gray end borrows the other end's hue, so the steps between them do not drift through a third hue."""
	(paper_chroma, paper_hue), (ink_chroma, ink_hue) = paper_tint, ink_tint
	if paper_chroma < GRAY_CHROMA:
		paper_hue = ink_hue
	if ink_chroma < GRAY_CHROMA:
		ink_hue = paper_hue
	return (paper_chroma, paper_hue), (ink_chroma, ink_hue)


def blend(step: tuple[float, float, float], paper_tint: tuple, ink_tint: tuple) -> str:
	"""The hex color of a ladder *step*, tinted between the paper and the ink."""
	lightness, share, chroma_scale = step
	(paper_chroma, paper_hue), (ink_chroma, ink_hue) = paper_tint, ink_tint
	turn = (ink_hue - paper_hue + math.pi) % (2 * math.pi) - math.pi
	chroma = (paper_chroma + (ink_chroma - paper_chroma) * share) * chroma_scale
	return to_hex(in_gamut(lightness, chroma, paper_hue + turn * share))


def clamp(color: str, lowest: float, highest: float, max_chroma: float) -> str:
	"""*color* with its OKLCH lightness moved into [lowest, highest] and its chroma capped, inside sRGB."""
	lightness, chroma, hue = to_oklch(color)
	return to_hex(in_gamut(min(max(lightness, lowest), highest), min(chroma, max_chroma), hue))


def in_gamut(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
	"""Linear sRGB of the OKLCH color, with chroma lowered until it fits inside sRGB."""
	while chroma > 0 and not is_in_srgb(from_oklch(lightness, chroma, hue)):
		chroma = max(chroma - 0.002, 0)
	return from_oklch(lightness, chroma, hue)


def to_oklch(color: str) -> tuple[float, float, float]:
	"""A hex color as OKLCH lightness, chroma and hue."""
	digits = color.strip().lstrip("#")
	if len(digits) == 3:
		digits = "".join(digit * 2 for digit in digits)
	red, green, blue = (to_linear(int(digits[index : index + 2], 16) / 255) for index in (0, 2, 4))

	long = math.cbrt(0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue)
	medium = math.cbrt(0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue)
	short = math.cbrt(0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue)

	lightness = 0.2104542553 * long + 0.7936177850 * medium - 0.0040720468 * short
	a = 1.9779984951 * long - 2.4285922050 * medium + 0.4505937099 * short
	b = 0.0259040371 * long + 0.7827717662 * medium - 0.8086757660 * short
	return lightness, math.hypot(a, b), math.atan2(b, a)


def from_oklch(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
	"""Linear sRGB (each channel may fall outside 0 to 1 when the color is out of gamut)."""
	a, b = chroma * math.cos(hue), chroma * math.sin(hue)
	long = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
	medium = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
	short = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
	return (
		4.0767416621 * long - 3.3077115913 * medium + 0.2309699292 * short,
		-1.2684380046 * long + 2.6097574011 * medium - 0.3413193965 * short,
		-0.0041960863 * long - 0.7034186147 * medium + 1.7076147010 * short,
	)


def is_in_srgb(channels: tuple[float, float, float]) -> bool:
	"""Whether every linear channel is inside the sRGB range."""
	return all(-0.0001 <= channel <= 1.0001 for channel in channels)


def to_hex(channels: tuple[float, float, float]) -> str:
	"""Linear sRGB channels as a hex color, clamped to the gamut."""
	return "#" + "".join(f"{round(min(max(to_gamma(channel), 0), 1) * 255):02x}" for channel in channels)


def to_linear(channel: float) -> float:
	"""A gamma-encoded sRGB channel as a linear one."""
	return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def to_gamma(channel: float) -> float:
	"""A linear sRGB channel as a gamma-encoded one."""
	return 12.92 * channel if channel <= 0.0031308 else 1.055 * max(channel, 0) ** (1 / 2.4) - 0.055
