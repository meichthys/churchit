# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import math
import os
import re
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.website.doctype.website_theme.website_theme import WebsiteTheme

from churchit.church_website import palette
from churchit.tests.helpers import forget_website_settings

PAPER = "#faf8f3"
LAMP_BLACK = "#1c1a17"
OKLCH = re.compile(r"--([\w-]+):\s*oklch\(([\d.]+) ([\d.]+) ([\d.]+)\)")


def contrast(first, second):
	def luminance(color):
		red, green, blue = (palette.to_linear(int(color[index : index + 2], 16) / 255) for index in (1, 3, 5))
		return 0.2126 * red + 0.7152 * green + 0.0722 * blue

	lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
	return (lighter + 0.05) / (darker + 0.05)


def member_app_tokens() -> dict[str, dict[str, str]]:
	"""The member app's own token blocks (frontend/src/style.css), as hex colors by mode."""
	path = os.path.join(frappe.get_app_path("churchit"), "..", "frontend", "src", "style.css")
	css = open(path).read()
	blocks = {"light": css.split(":root {", 1)[1], "dark": css.split('[data-theme="dark"] {', 1)[1]}
	return {
		mode: {
			token: palette.to_hex(
				palette.from_oklch(float(lightness), float(chroma), math.radians(float(hue)))
			)
			for token, lightness, chroma, hue in OKLCH.findall(block.split("}", 1)[0])
		}
		for mode, block in blocks.items()
	}


class TestPalette(FrappeTestCase):
	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		forget_website_settings()
		frappe.set_user("Administrator")

	def test_any_church_color_reads_as_text_in_both_themes(self):
		for source in ("#9b2f22", "#3b82f6", "#f2c14e", "#22c55e", "#000", "#ffffff", "#808080", "#6366f1"):
			light = palette.clamp(source, *palette.LIGHT_BAND)
			dark = palette.clamp(source, *palette.DARK_BAND)
			self.assertGreaterEqual(contrast(light, PAPER), 4.5, source)
			self.assertGreaterEqual(contrast(dark, LAMP_BLACK), 4.5, source)

	def test_a_color_already_in_the_band_keeps_its_value(self):
		accent = palette.DEFAULT_PALETTE[2]
		self.assertEqual(palette.clamp(accent, *palette.LIGHT_BAND), accent)

	def test_a_theme_color_that_is_not_a_hex_color_is_ignored(self):
		for value in ("red", "url(x)", "#12345g", ""):
			self.assertIsNone(palette.HEX_COLOR.fullmatch(value), value)

	def test_the_churchit_palette_is_the_member_app_look(self):
		"""The default palette and the app's fallback tokens are one look; change both together."""
		tokens = palette.make_tokens(*palette.PALETTES["Churchit"])
		for mode, expected in member_app_tokens().items():
			for token, color in expected.items():
				made = tokens[mode][token]
				drift = max(abs(int(color[i : i + 2], 16) - int(made[i : i + 2], 16)) for i in (1, 3, 5))
				self.assertLessEqual(drift, 2, f"{mode} {token}: app {color}, palette {made}")

	def test_every_shipped_palette_keeps_its_text_readable(self):
		for theme, colors in palette.PALETTES.items():
			for mode, tokens in palette.make_tokens(*colors).items():
				paper = tokens["surface-base"]
				for token in ("ink-gray-5", "ink-gray-8", "accent"):
					self.assertGreaterEqual(contrast(tokens[token], paper), 4.5, f"{theme} {mode} {token}")

	def test_a_gray_paper_takes_the_hue_of_the_ink(self):
		ink_hue = palette.to_oklch("#0c1117")[2]
		tokens = palette.make_tokens("#ffffff", "#0c1117", "#1f4e8c")["light"]
		_lightness, chroma, hue = palette.to_oklch(tokens["surface-gray-7"])
		self.assertGreater(chroma, 0.003)
		self.assertLess(abs(math.remainder(hue - ink_hue, 2 * math.pi)), 0.3)

	def test_the_style_names_every_token_for_both_modes(self):
		style = palette.make_style(*palette.PALETTES["Harbor"])
		self.assertTrue(style.startswith('<style id="churchit-palette">html:root{'))
		self.assertIn('html[data-theme="dark"]{', style)
		for token in [*palette.LIGHT_LADDER, "accent"]:
			self.assertEqual(style.count(f"--{token}:"), 2, token)

	def test_a_theme_takes_its_colors_and_the_default_for_any_it_leaves_empty(self):
		self.enterContext(patch.object(WebsiteTheme, "generate_bootstrap_theme"))
		frappe.get_doc({"doctype": "Color", "name": "_Test Palette Paper", "color": "#f7fbfe"}).insert()
		theme = frappe.get_doc(
			{
				"doctype": "Website Theme",
				"theme": "_Test Palette Theme",
				"background_color": "_Test Palette Paper",
			}
		).insert()

		self.assertEqual(palette.get_theme_palette(theme.name), ("#f7fbfe", *palette.DEFAULT_PALETTE[1:]))
		self.assertIsNone(palette.get_theme_palette("_Test Missing Theme"))

	def test_the_accent_follows_the_theme_and_the_app_keeps_its_own_on_standard(self):
		frappe.local.website_settings = frappe._dict(website_theme="Harbor")
		self.assertEqual(
			palette.get_accent()["light"],
			palette.clamp(palette.get_theme_palette("Harbor")[2], *palette.LIGHT_BAND),
		)
		frappe.local.website_settings = frappe._dict(website_theme="Standard")
		self.assertEqual(palette.get_accent()["light"], palette.DEFAULT_PALETTE[2])

	def test_a_changed_color_of_the_website_theme_clears_the_page_cache(self):
		frappe.local.website_settings = frappe._dict(website_theme="Churchit")
		clear = self.enterContext(patch("churchit.church_website.palette.clear_website_cache"))
		accent = frappe.db.get_value("Website Theme", "Churchit", "primary_color")

		palette.clear_pages_on_color_change(frappe._dict(name="_Test Unused Color"))
		clear.assert_not_called()
		palette.clear_pages_on_color_change(frappe._dict(name=accent))
		clear.assert_called_once()

	def test_the_standard_theme_keeps_frappe_s_colors(self):
		frappe.local.website_settings = frappe._dict(website_theme="Standard")
		self.assertEqual(palette.get_palette_style(), "")
		self.assertIsNone(palette.get_theme_color())

	def test_a_theme_s_paper_colors_the_browser(self):
		frappe.local.website_settings = frappe._dict(website_theme="Churchit")
		self.assertIn(palette.make_style(*palette.get_theme_palette("Churchit")), palette.get_palette_style())
		paper = palette.make_tokens(*palette.get_theme_palette("Churchit"))
		self.assertEqual(palette.get_theme_color()["light"], paper["light"]["surface-base"])

	def test_only_someone_who_may_change_website_settings_previews_a_theme(self):
		self.assertNotEqual(palette.get_theme_palette("Harbor"), palette.get_theme_palette("Churchit"))
		frappe.local.website_settings = frappe._dict(website_theme="Churchit")
		frappe.local.form_dict = frappe._dict(theme_preview="Harbor")
		self.assertEqual(palette.get_website_palette(), palette.get_theme_palette("Harbor"))

		frappe.set_user("Guest")
		self.assertEqual(palette.get_website_palette(), palette.get_theme_palette("Churchit"))
