# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member app's one accent color: the church's Website Theme color, kept readable in both themes.

The accent marks only "now" and "do this" (today's date, an instruction, a line a live update changed),
so any brand color has to pass as text on the app's paper and on its dark page. Its hue is kept and its
OKLCH lightness forced into a band, with chroma capped so no color shouts. Browsers that lack CSS relative
colors get the two results ready made.
"""

import math
import re

import frappe

# Rubric red, the red of the instructions in a printed order of service.
DEFAULT_ACCENT = "#9b2f22"
HEX_COLOR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
# (lowest lightness, highest lightness, highest chroma) on the light paper and on the dark page.
LIGHT_BAND = (0.40, 0.50, 0.16)
DARK_BAND = (0.74, 0.82, 0.13)


def get_accent() -> dict[str, str]:
	"""The accent for the light and the dark theme, as hex colors."""
	source = get_theme_color() or DEFAULT_ACCENT
	return {"light": clamp(source, *LIGHT_BAND), "dark": clamp(source, *DARK_BAND)}


def get_theme_color() -> str | None:
	"""The primary color of the website's theme, when it is a hex color."""
	theme = frappe.get_cached_value("Website Settings", None, "website_theme")
	color = theme and frappe.get_cached_value("Website Theme", theme, "primary_color")
	return color if color and HEX_COLOR.fullmatch(color.strip()) else None


def clamp(color: str, lowest: float, highest: float, max_chroma: float) -> str:
	"""*color* with its OKLCH lightness moved into [lowest, highest] and its chroma capped, inside sRGB."""
	lightness, chroma, hue = to_oklch(color)
	lightness = min(max(lightness, lowest), highest)
	chroma = min(chroma, max_chroma)
	while chroma > 0 and not is_in_srgb(from_oklch(lightness, chroma, hue)):
		chroma = max(chroma - 0.002, 0)
	return to_hex(from_oklch(lightness, chroma, hue))


def to_oklch(color: str) -> tuple[float, float, float]:
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
	return all(-0.0001 <= channel <= 1.0001 for channel in channels)


def to_hex(channels: tuple[float, float, float]) -> str:
	return "#" + "".join(f"{round(min(max(to_gamma(channel), 0), 1) * 255):02x}" for channel in channels)


def to_linear(channel: float) -> float:
	return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def to_gamma(channel: float) -> float:
	return 12.92 * channel if channel <= 0.0031308 else 1.055 * max(channel, 0) ** (1 / 2.4) - 0.055
