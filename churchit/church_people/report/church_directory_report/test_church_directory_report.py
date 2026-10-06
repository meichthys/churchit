# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import io

import frappe
from frappe.tests.utils import FrappeTestCase
from pypdf import PdfReader

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

	def test_booklet_pages_are_added_only_when_ticked(self):
		html = self.render()
		self.assertNotIn('<div class="blank-page">', html)
		self.assertNotIn("counter(page)", html)
		self.assertNotIn('<div class="note-line">', html)

		html = self.render(blank_back_cover="1", show_page_numbers="1", include_notes_page="1")
		self.assertIn('<div class="blank-page">', html)
		self.assertIn("counter(page)", html)
		self.assertEqual(html.count('<div class="note-line">'), 24)

	def render_pdf_pages(self, **options):
		download_directory_pdf(church=self.church, include_notes_page="1", **options)
		self.addCleanup(frappe.local.response.pop, "filecontent", None)
		return [
			page.extract_text().split()
			for page in PdfReader(io.BytesIO(frappe.local.response.filecontent)).pages
		]

	def test_pdf_numbers_the_pages_and_ends_on_a_blank_back_cover(self):
		plain = self.render_pdf_pages()
		booklet = self.render_pdf_pages(show_page_numbers="1", blank_back_cover="1")

		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertEqual(len(booklet), len(plain) + 1)
		self.assertEqual(booklet[0], plain[0])
		notes_page = str(len(plain))
		self.assertEqual(booklet[-2].count(notes_page), plain[-1].count(notes_page) + 1)
		self.assertEqual(booklet[-1], [])
