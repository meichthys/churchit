# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import io

import frappe
from frappe.tests.utils import FrappeTestCase
from pypdf import PdfReader

from churchit.church_people.report.church_directory_report.booklet import SHEET_WIDTH, get_booklet_spreads
from churchit.church_people.report.church_directory_report.church_directory_report import (
	download_directory_pdf,
	get_directory_html,
)
from churchit.tests.helpers import ensure_root_church, make_translation


class TestChurchDirectoryReport(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.church = ensure_root_church()

	def render(self, **options):
		return get_directory_html(church=self.church, **options)

	def set_church_value(self, fieldname, value):
		original = frappe.db.get_value("Church", self.church, fieldname)
		frappe.db.set_value("Church", self.church, fieldname, value)
		self.addCleanup(frappe.db.set_value, "Church", self.church, fieldname, original)

	def set_website_feature(self, enabled):
		original = frappe.db.get_single_value("Church Features", "enable_website")
		frappe.db.set_single_value("Church Features", "enable_website", enabled)
		self.addCleanup(frappe.db.set_single_value, "Church Features", "enable_website", original)

	def test_cover_shows_the_church_verse_and_website(self):
		translation = make_translation(self, "_TDV", [("JOS", 24, 15, "We will serve the LORD.")])
		self.set_church_value("default_bible_translation", translation)
		self.set_church_value("church_verse", "Joshua 24:15")
		self.set_website_feature(1)

		html = self.render()

		self.assertIn("We will serve the LORD.", html)
		self.assertIn(f"Joshua 24:15 ({translation})", html)
		website = frappe.utils.get_url().split("://", 1)[-1]
		self.assertIn(f'<div class="cover-website">{website}</div>', html)

	def test_cover_leaves_out_the_website_when_the_web_site_module_is_off(self):
		self.set_website_feature(0)

		self.assertNotIn('<div class="cover-website">', self.render())

	def test_cover_shows_the_church_image_only_when_ticked(self):
		self.set_church_value("image", "/files/_test_church.png")

		self.assertNotIn('class="cover-image"', self.render())
		self.assertIn(
			'<img class="cover-image" src="/files/_test_church.png"', self.render(show_church_image="1")
		)

	def test_cover_leaves_out_the_mission_statement(self):
		self.set_church_value("mission_statement", "_Test mission statement")

		self.assertNotIn("_Test mission statement", self.render())

	def test_booklet_pages_are_added_only_when_ticked(self):
		html = self.render()
		self.assertNotIn('<div class="blank-page">', html)
		self.assertNotIn("counter(page)", html)
		self.assertNotIn('<div class="note-line">', html)

		html = self.render(blank_back_cover="1", show_page_numbers="1", include_notes_page="1")
		self.assertIn('<div class="blank-page">', html)
		self.assertIn("counter(page)", html)
		self.assertEqual(html.count('<div class="note-line">'), 24)

	def render_pdf(self, **options):
		download_directory_pdf(church=self.church, **options)
		self.addCleanup(frappe.local.response.pop, "filecontent", None)
		return PdfReader(io.BytesIO(frappe.local.response.filecontent)).pages

	def render_pdf_pages(self, **options):
		return [page.extract_text().split() for page in self.render_pdf(include_notes_page="1", **options)]

	def test_pdf_numbers_the_pages_and_ends_on_a_blank_back_cover(self):
		plain = self.render_pdf_pages()
		booklet = self.render_pdf_pages(show_page_numbers="1", blank_back_cover="1")

		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertEqual(len(booklet), len(plain) + 1)
		self.assertEqual(booklet[0], plain[0])
		notes_page = str(len(plain))
		self.assertEqual(booklet[-2].count(notes_page), plain[-1].count(notes_page) + 1)
		self.assertEqual(booklet[-1], [])

	def test_booklet_spreads_fold_into_page_order(self):
		folded = [(8, 1), (2, 7), (6, 3), (4, 5)]
		self.assertEqual(get_booklet_spreads(8), folded)
		self.assertEqual(get_booklet_spreads(5), folded)

	def test_booklet_pdf_puts_the_cover_in_front_and_page_numbers_on_the_outer_edge(self):
		cover = "".join(word for x, word in get_positioned_words(self.render_pdf()[0]))
		sides = self.render_pdf(booklet_printing="1", show_page_numbers="1")

		self.assertEqual({(side.mediabox.width, side.mediabox.height) for side in sides}, {(792, 612)})
		self.assertEqual(len(sides) % 2, 0)
		front = get_positioned_words(sides[0])
		self.assertEqual([word for x, word in front if x < SHEET_WIDTH / 2], [])
		self.assertEqual("".join(word for x, word in front if x >= SHEET_WIDTH / 2), cover)
		page_two_number = [x for x, word in get_positioned_words(sides[1]) if word == "2"]
		self.assertEqual(len(page_two_number), 1)
		self.assertLess(page_two_number[0], SHEET_WIDTH / 8)

	def test_booklet_pads_before_the_notes_page_so_it_stays_inside_the_back_cover(self):
		sides = self.render_pdf(booklet_printing="1", show_page_numbers="1", include_notes_page="1")

		inside_back_cover = [word for x, word in get_positioned_words(sides[1]) if x >= SHEET_WIDTH / 2]
		self.assertEqual(inside_back_cover[0], "Notes")
		self.assertIn(str(len(sides) * 2 - 1), inside_back_cover)


def get_positioned_words(page):
	"""Each word on the page with the x position of the text run it is in."""
	words = []

	def visit(text, cm, tm, font, size):
		x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
		words.extend((x, word) for word in text.split())

	page.extract_text(visitor_text=visit)
	return words
