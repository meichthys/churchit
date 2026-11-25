# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.tests.utils import FrappeTestCase

from churchit.portal import accent

PAPER = "#faf8f3"
LAMP_BLACK = "#1c1a17"


def contrast(first, second):
	def luminance(color):
		red, green, blue = (accent.to_linear(int(color[index : index + 2], 16) / 255) for index in (1, 3, 5))
		return 0.2126 * red + 0.7152 * green + 0.0722 * blue

	lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
	return (lighter + 0.05) / (darker + 0.05)


class TestAccent(FrappeTestCase):
	def test_any_church_color_reads_as_text_in_both_themes(self):
		for source in ("#9b2f22", "#3b82f6", "#f2c14e", "#22c55e", "#000", "#ffffff", "#808080", "#6366f1"):
			light = accent.clamp(source, *accent.LIGHT_BAND)
			dark = accent.clamp(source, *accent.DARK_BAND)
			self.assertGreaterEqual(contrast(light, PAPER), 4.5, source)
			self.assertGreaterEqual(contrast(dark, LAMP_BLACK), 4.5, source)

	def test_a_color_already_in_the_band_keeps_its_value(self):
		self.assertEqual(accent.clamp(accent.DEFAULT_ACCENT, *accent.LIGHT_BAND), accent.DEFAULT_ACCENT)

	def test_a_theme_color_that_is_not_a_hex_color_is_ignored(self):
		for value in ("red", "url(x)", "#12345g", ""):
			self.assertIsNone(accent.HEX_COLOR.fullmatch(value), value)
