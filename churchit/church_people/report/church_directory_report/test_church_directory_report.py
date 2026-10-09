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
from churchit.tests.helpers import ensure_root_church, make_address, make_person, make_translation


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

	def test_contact_details_are_printed_only_when_ticked(self):
		family = make_family("_Test Directory Contacts", "_Test Directory Lane")
		make_person(
			"_Test",
			"Directory Contacts",
			family=family.name,
			phones=[{"phone_number": "202-555-0187", "is_primary": 1}],
			emails=[{"email_address": "_test.directory@example.com", "is_primary": 1}],
		)
		missionary_email = "_test.directory.missionary@example.com"
		frappe.get_doc(
			{
				"doctype": "Missionary",
				"title": "_Test Directory Missionary",
				"emails": [{"email_address": missionary_email, "is_primary": 1}],
			}
		).insert(ignore_permissions=True)
		contact_details = [
			"202-555-0187",
			"_test.directory@example.com",
			"_Test Directory Lane",
			missionary_email,
		]

		html = self.render(show_missionaries="1")
		for detail in contact_details:
			self.assertIn(detail, html)
		self.assertIn("<th>Phone</th><td>202-555-0187</td>", html)
		self.assertIn("<th>Email</th><td>_test.directory@example.com</td>", html)

		html = self.render(show_missionaries="1", show_phone="0", show_email="0", show_address="0")
		for detail in contact_details:
			self.assertNotIn(detail, html)
		self.assertNotIn("<th>Phone</th>", html)
		self.assertNotIn("<th>Email</th>", html)

	def test_people_print_their_own_address_else_their_familys(self):
		family = make_family("_Test Directory Household", "_Test Family Street")
		make_person("_Test", "Directory Member", family=family.name)
		away = make_address("_Test Directory Away", address_line1="_Test Away Street").name
		make_person(
			"_Test", "Directory Away", family=family.name, addresses=[{"address": away, "is_primary": 1}]
		)
		single = make_address("_Test Directory Single", address_line1="_Test Single Street").name
		make_person("_Test", "Directory Single", addresses=[{"address": single, "is_primary": 1}])

		grouped = self.render()
		self.assertEqual(grouped.count("_Test Family Street"), 1)
		self.assertIn("<th>Address</th><td>_Test Away Street, Springfield", grouped)
		self.assertIn("<th>Address</th><td>_Test Single Street, Springfield", grouped)
		self.assertEqual(grouped.count("_Test Directory Single"), 1, "an entry of its own restates the name")
		for html in (grouped, self.render(group_by_family="0")):
			self.assertIn("_Test Family Street", html)
			self.assertIn("_Test Away Street", html)
			self.assertIn("_Test Single Street", html)
		html = self.render(show_address="0")
		for street in ("_Test Family Street", "_Test Away Street", "_Test Single Street"):
			self.assertNotIn(street, html)

	def test_hidden_people_are_left_out_everywhere(self):
		family = make_family("_Test Hidden - Hal", "_Test Hidden Street")
		born = [{"event_type": "Birth", "date": "1980-05-05"}]
		hal = make_person(
			"_Test Hal",
			"Hidden",
			family=family.name,
			is_head_of_household=1,
			hide_from_directory=1,
			life_events=born,
		)
		make_person(
			"_Test Wanda",
			"Hidden",
			family=family.name,
			spouse=hal.name,
			is_married=1,
			anniversary="2005-06-06",
			life_events=born,
		)
		make_person("_Test Solo", "Hidden", hide_from_directory=1)
		everyone_hidden = make_family("_Test Gone - Gus", "_Test Gone Street")
		make_person("_Test Gus", "Gone", family=everyone_hidden.name, hide_from_directory=1)

		options = {"show_birthdays": "1", "show_anniversaries": "1"}
		grouped = self.render(**options)
		self.assertIn("_Test Hidden Family", grouped)
		self.assertIn("_Test Wanda Hidden", grouped)
		self.assertNotIn("_Test Gone", grouped)
		self.assertNotIn("_Test Wanda &amp;", grouped, "an anniversary would name the hidden spouse")
		for html in (grouped, self.render(group_by_family="0", **options)):
			self.assertNotIn("Hal", html)
			self.assertNotIn("_Test Solo", html)
			self.assertNotIn("_Test Gus", html)

	def test_missionaries_are_listed_once_when_their_section_is_ticked(self):
		make_person("_Test", "Directory Neighbor")
		missionary = make_person("_Test", "Directory Sent")
		frappe.get_doc(
			{
				"doctype": "Missionary",
				"title": "_Test Directory Sent Family",
				"people": [{"person": missionary.name}],
			}
		).insert(ignore_permissions=True)

		self.assertIn("Directory Sent</", self.render())
		html = self.render(show_missionaries="1")
		self.assertIn("_Test Directory Sent Family", html)
		self.assertNotIn("Directory Sent</", html)
		self.assertIn("Directory Neighbor</", html)

	def test_record_values_are_escaped(self):
		self.set_church_value("church_name", 'Saint "Mary" </style><script>x()</script>')
		make_person("_Test", "<b>Directory Escaped</b>", photo='/files/_test.png" onerror="alert(1)')

		html = self.render(show_photos="1")

		self.assertNotIn("<script>", html)
		self.assertNotIn("<b>Directory Escaped</b>", html)
		self.assertIn("&lt;b&gt;Directory Escaped&lt;/b&gt;", html)
		self.assertNotIn('onerror="alert(1)"', html)

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


def make_family(family_name, street):
	"""A Family whose primary address is on *street*."""
	address = make_address(f"{family_name} Home", address_line1=street).name
	return frappe.get_doc(
		{
			"doctype": "Family",
			"family_name": family_name,
			"addresses": [{"address": address, "is_primary": 1}],
		}
	).insert(ignore_permissions=True)


def get_positioned_words(page):
	"""Each word on the page with the x position of the text run it is in."""
	words = []

	def visit(text, cm, tm, font, size):
		x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
		words.extend((x, word) for word in text.split())

	page.extract_text(visitor_text=visit)
	return words
