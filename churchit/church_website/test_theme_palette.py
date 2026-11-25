# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_website.palette import PALETTES, get_theme_palette, make_tokens
from churchit.church_website.theme_palette import get_website_theme_palette, get_website_theme_palettes


class TestThemePalette(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_the_picker_lists_the_shipped_palettes_first_and_standard_last(self):
		names = [theme["name"] for theme in get_website_theme_palettes()]
		shipped = [name for name in PALETTES if name in names]
		self.assertEqual(names[: len(shipped)], shipped)
		self.assertEqual(names[-1], "Standard")

	def test_each_theme_shows_its_light_and_dark_page(self):
		churchit = next(theme for theme in get_website_theme_palettes() if theme["name"] == "Churchit")
		tokens = make_tokens(*get_theme_palette("Churchit"))
		for mode in ("light", "dark"):
			self.assertEqual(churchit[mode]["paper"], tokens[mode]["surface-base"])
			self.assertEqual(churchit[mode]["accent"], tokens[mode]["accent"])
			self.assertEqual(set(churchit[mode]), {"paper", "ink", "muted", "rule", "accent"})

	def test_the_swatches_of_one_theme(self):
		labels = [swatch["label"] for swatch in get_website_theme_palette("Churchit")]
		self.assertEqual(labels, ["Accent", "Background", "Text"])
		self.assertEqual(len(get_website_theme_palette("Standard")), 3)
		self.assertEqual(get_website_theme_palette("_Missing Theme"), [])

	def test_a_guest_may_not_read_the_themes(self):
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, get_website_theme_palettes)
