# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.tests.utils import FrappeTestCase

from churchit.church_website.theme_palette import (
	get_root_tokens,
	get_website_theme_palette,
	resolve_color,
)

CSS = """
:root {
  --gray-900: #171717;
  --primary: var(--gray-900);
  --bg-color: white;
  --grad: linear-gradient(90deg, red, blue);
}
:root,
[data-theme="light"] {
  --text-color: rgb(56, 56, 56);
}
:root[data-theme=dark] {
  --bg-color: black;
}
@media (prefers-color-scheme: dark) { :root { --text-color: #fff; } }
:root { --gray-900: #000000; }
"""


class TestThemePalette(FrappeTestCase):
	def test_root_tokens_follow_cascade_and_skip_dark_blocks(self):
		tokens = get_root_tokens(CSS)
		self.assertEqual(tokens["--bg-color"], "white")
		self.assertEqual(tokens["--text-color"], "rgb(56, 56, 56)")
		self.assertEqual(tokens["--gray-900"], "#000000", "a later :root block wins")

	def test_resolve_color_follows_var_chains_and_rejects_gradients(self):
		tokens = get_root_tokens(CSS)
		self.assertEqual(resolve_color(tokens, "--primary"), "#000000")
		self.assertEqual(resolve_color(tokens, "--text-color"), "rgb(56, 56, 56)")
		self.assertIsNone(resolve_color(tokens, "--grad"))
		self.assertIsNone(resolve_color(tokens, "--missing"))

	def test_churchit_theme_shows_its_brand_colors(self):
		labels = [swatch["label"] for swatch in get_website_theme_palette("Churchit")]
		self.assertEqual(labels, ["Brand", "Accent", "Accent", "Background", "Text"])

	def test_standard_theme_reads_the_website_bundle(self):
		palette = {swatch["label"]: swatch["color"] for swatch in get_website_theme_palette("Standard")}
		self.assertEqual(set(palette), {"Primary", "Background", "Text"})
		self.assertTrue(palette["Primary"].startswith("#"))

	def test_unknown_theme_has_no_palette(self):
		self.assertEqual(get_website_theme_palette("_Missing Theme"), [])
