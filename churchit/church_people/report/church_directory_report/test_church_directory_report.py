# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import base64
import io

import frappe
from frappe.tests.utils import FrappeTestCase
from PIL import Image
from pypdf import PdfReader

from churchit.church_people.report.church_directory_report.booklet import SHEET_WIDTH, get_booklet_spreads
from churchit.church_people.report.church_directory_report.church_directory_report import (
	download_directory_pdf,
	execute,
	get_directory_html,
	get_paginated_directory,
)
from churchit.tests.helpers import (
	ensure,
	ensure_root_church,
	ensure_user,
	make_address,
	make_person,
	make_primary_contact,
	make_translation,
)


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

	def test_only_users_the_report_allows_get_the_directory(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(ensure_user("_test_directory_member@example.com", "Member", roles=("Church User",)))

		with self.assertRaises(frappe.PermissionError):
			self.render()
		with self.assertRaises(frappe.PermissionError):
			download_directory_pdf(church=self.church)

	def test_cover_shows_the_church_verse_and_website(self):
		translation = make_translation(self, "_TDV", [("JOS", 24, 15, "We will serve the LORD.")])
		self.set_church_value("default_bible_translation", translation)
		self.set_church_value("church_verse", "Joshua 24:15")
		self.set_church_value("website", "https://test-church.example.org/")

		html = self.render()

		self.assertIn("We will serve the LORD.", html)
		self.assertIn(f"Joshua 24:15 ({translation})", html)
		self.assertIn('<div class="cover-website">test-church.example.org</div>', html)

	def test_cover_leaves_out_the_website_when_the_church_has_none(self):
		self.set_church_value("website", None)
		self.set_website_feature(1)

		self.assertNotIn('<div class="cover-website">', self.render())

	def test_cover_shows_the_church_image_only_when_ticked(self):
		self.set_church_value("image", "/files/_test_church.png")

		self.assertNotIn('class="cover-image"', self.render())
		self.assertIn(
			'<img class="cover-image" src="/files/_test_church.png"', self.render(show_church_image="1")
		)

	def test_cover_image_fills_the_space_under_the_text_on_one_page(self):
		for width, height in ((1600, 900), (600, 1200)):
			self.set_church_value("image", make_png_data_uri(width, height))
			for booklet in ("0", "1"):
				with self.subTest(image=(width, height), booklet=booklet):
					options = {"church": self.church, "show_church_image": "1", "booklet_printing": booklet}
					html = get_directory_html(**options)
					self.assertGreater(html.index('class="cover-image"'), html.index('class="cover-date"'))

					pages = get_paginated_directory(options).pages
					image = find_box(pages[0]._page_box, "img")
					self.assertGreater(
						image.height, MM_TO_PX * 100, "the image takes the space left on the cover"
					)
					self.assertIsNone(find_box(pages[1]._page_box, "img"), "the image stays on the cover")

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
		hal = make_primary_contact(
			make_person(
				"_Test Hal",
				"Hidden",
				family=family.name,
				hide_from_directory=1,
				life_events=born,
			)
		)
		make_person(
			"_Test Wanda",
			"Hidden",
			family=family.name,
			spouse=hal.name,
			marital_status="Married",
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

	def test_anniversaries_name_only_the_spouses(self):
		family = make_family("_Test Wed - Carl", "_Test Wed Street")
		carl = make_primary_contact(make_person("_Test Carl", "Wed", family=family.name))
		make_person(
			"_Test Dana",
			"Wed",
			family=family.name,
			spouse=carl.name,
			marital_status="Married",
			anniversary="2003-03-03",
		)
		eve = make_person("_Test Eve", "Pine")
		make_person("_Test Finn", "Oak", spouse=eve.name, marital_status="Married", anniversary="2004-04-04")

		html = self.render(show_anniversaries="1")

		self.assertIn('<span class="calendar-name">_Test Carl &amp; _Test Dana Wed</span>', html)
		self.assertIn('<span class="calendar-name">_Test Finn Oak &amp; _Test Eve Pine</span>', html)

	def test_family_relationships_are_printed_only_when_ticked(self):
		family = make_family("_Test Kin - Gil", "_Test Kin Street")
		gil = make_primary_contact(make_person("_Test Gil", "Kin", family=family.name, gender="Male"))
		make_person(
			"_Test Hope",
			"Kin",
			family=family.name,
			spouse=gil.name,
			marital_status="Married",
			gender="Female",
		)

		html = self.render()
		self.assertIn('<span class="member-relation">(Husband)</span>', html)
		self.assertIn('<span class="member-relation">(Wife)</span>', html)
		self.assertNotIn('class="member-relation"', self.render(show_relationships="0"))

	def test_families_list_the_primary_contact_and_spouse_before_the_others(self):
		family = make_family("_Test Order - Zed", "_Test Order Street")
		zed = make_primary_contact(make_person("_Test Zed", "Order", family=family.name))
		make_person("_Test Yara", "Order", family=family.name, spouse=zed.name, marital_status="Married")
		make_person("_Test Abby", "Order", family=family.name)
		unlisted_head = make_family("_Test Unlisted - Vic", "_Test Unlisted Street")
		vic = make_primary_contact(
			make_person("_Test Vic", "Unlisted", family=unlisted_head.name, hide_from_directory=1)
		)
		make_person(
			"_Test Wren", "Unlisted", family=unlisted_head.name, spouse=vic.name, marital_status="Married"
		)
		make_person("_Test Ada", "Unlisted", family=unlisted_head.name)

		html = self.render()

		names = ("_Test Zed Order", "_Test Yara Order", "_Test Abby Order")
		self.assertEqual([html.index(name) for name in names], sorted(html.index(name) for name in names))
		self.assertLess(html.index("_Test Wren Unlisted"), html.index("_Test Ada Unlisted"))

	def test_people_who_are_not_active_are_left_out_only_when_ticked(self):
		ensure("Member Status", {"status": "Inactive"})
		ensure("Member Status", {"status": "_Test Homebound"})
		family = make_family("_Test Lapsed - Ivy", "_Test Lapsed Street")
		born = [{"event_type": "Birth", "date": "1980-07-07"}]
		ivy = make_primary_contact(
			make_person(
				"_Test Ivy",
				"Lapsed",
				family=family.name,
				membership_status="Inactive",
				life_events=born,
			)
		)
		make_person(
			"_Test Abe",
			"Lapsed",
			family=family.name,
			spouse=ivy.name,
			marital_status="Married",
			anniversary="2001-08-08",
		)
		make_person("_Test Solo", "Lapsed", membership_status="_Test Homebound")

		options = {"show_birthdays": "1", "show_anniversaries": "1"}
		self.assertIn("_Test Ivy", self.render(**options))
		grouped = self.render(hide_non_active="1", **options)
		self.assertIn("_Test Lapsed Family", grouped)
		for html in (grouped, self.render(hide_non_active="1", group_by_family="0", **options)):
			self.assertIn("_Test Abe Lapsed", html)
			self.assertNotIn("Ivy", html, "an anniversary would name the inactive spouse")
			self.assertNotIn("_Test Solo Lapsed", html)
		people = [row["person"] for row in execute({"group_by_family": 0, "hide_non_active": 1})[1]]
		self.assertNotIn(ivy.name, people)

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
		self.assertEqual(html.count("Directory Sent</"), 1)
		self.assertIn('<div class="missionary-people">_Test Directory Sent</div>', html)
		self.assertIn("Directory Neighbor</", html)

	def test_missionaries_list_their_people_and_leave_out_inactive_ones(self):
		ensure("Missionary Status", {"status": "Inactive"})
		sent = make_person("_Test Sent", "Kinley")
		shy = make_person("_Test Shy", "Kinley", hide_from_directory=1)
		frappe.get_doc(
			{
				"doctype": "Missionary",
				"title": "_Test Kinley Family",
				"people": [{"person": sent.name}, {"person": shy.name}],
			}
		).insert(ignore_permissions=True)
		former = make_person("_Test Former", "Ashby")
		frappe.get_doc(
			{
				"doctype": "Missionary",
				"title": "_Test Ashby Family",
				"status": "Inactive",
				"people": [{"person": former.name}],
			}
		).insert(ignore_permissions=True)

		html = self.render(show_missionaries="1")

		self.assertIn('<div class="missionary-people">_Test Sent Kinley</div>', html)
		self.assertNotIn("_Test Ashby Family", html)
		self.assertIn(
			"_Test Former Ashby</", html, "an inactive missionary's people are listed with everyone"
		)

	def test_groups_are_listed_only_when_ticked(self):
		make_group("_Test Directory Choir", description="_Test sings on Sundays")

		self.assertNotIn("_Test Directory Choir", self.render())
		html = self.render(show_groups="1")
		self.assertIn('<div class="group-name">_Test Directory Choir</div>', html)
		self.assertIn('<div class="group-description">_Test sings on Sundays</div>', html)

	def test_groups_list_members_and_roles_only_when_shown_in_the_directory(self):
		ensure("Group Role", {"role": "Leader"})
		lead = make_person("_Test Lead", "Choir")
		shy = make_person("_Test Shy", "Choir", hide_from_directory=1)
		drummer = make_person("_Test Drummer", "Band")
		make_group(
			"_Test Directory Choir",
			show_in_directory=1,
			members=[{"person": lead.name, "group_role": "Leader"}, {"person": shy.name}],
		)
		make_group("_Test Directory Band", members=[{"person": drummer.name, "group_role": "Leader"}])
		member = '<span class="group-member-name">{}</span>'
		role = '<span class="group-member-role">Leader</span>'

		self.assertNotIn(member.format("_Test Lead Choir"), self.render(show_groups="1"))
		html = self.render(show_group_members="1", show_group_roles="1")
		self.assertNotIn('<div class="group-name">', html, "members need the group list")

		html = self.render(show_groups="1", show_group_members="1")
		self.assertIn(member.format("_Test Lead Choir"), html)
		self.assertNotIn(member.format("_Test Shy Choir"), html)
		self.assertNotIn(member.format("_Test Drummer Band"), html)
		self.assertNotIn(role, html)
		self.assertIn(role, self.render(show_groups="1", show_group_members="1", show_group_roles="1"))

	def test_group_members_are_listed_by_first_name(self):
		people = [make_person(first, "Sorted") for first in ("_Test Zoe", "_Test Abe", "_Test Max")]
		make_group(
			"_Test Directory Sorted",
			show_in_directory=1,
			members=[{"person": person.name} for person in people],
		)

		html = self.render(show_groups="1", show_group_members="1")

		names = [f">{first} Sorted<" for first in ("_Test Abe", "_Test Max", "_Test Zoe")]
		self.assertEqual([html.index(name) for name in names], sorted(html.index(name) for name in names))

	def test_inactive_groups_are_left_out(self):
		ensure("Group Status", {"status": "Inactive"})
		make_group("_Test Directory Disbanded", status="Inactive")

		self.assertNotIn("_Test Directory Disbanded", self.render(show_groups="1"))

	def test_deceased_people_are_left_out_everywhere(self):
		for event_type in ("Birth", "Death"):
			ensure("Life Event Type", {"type": event_type})
		family = make_family("_Test Mourning - Walt", "_Test Mourning Street")
		walt = make_primary_contact(
			make_person(
				"_Test Walt",
				"Mourning",
				family=family.name,
				life_events=[
					{"event_type": "Birth", "date": "1950-09-09"},
					{"event_type": "Death", "date": "2024-01-01"},
				],
			)
		)
		make_person(
			"_Test Rose",
			"Mourning",
			family=family.name,
			spouse=walt.name,
			marital_status="Married",
			anniversary="1975-10-10",
			life_events=[{"event_type": "Birth", "date": "1952-09-10"}],
		)

		options = {"show_birthdays": "1", "show_anniversaries": "1"}
		grouped = self.render(**options)
		self.assertIn("_Test Mourning Family", grouped)
		for html in (grouped, self.render(group_by_family="0", **options)):
			self.assertIn("_Test Rose Mourning", html)
			self.assertNotIn("Walt", html)

	def test_a_birthday_with_no_year_is_listed_by_month_and_day(self):
		ensure("Life Event Type", {"type": "Birth"})
		make_person(
			"_Test Yearless",
			"Birthday",
			life_events=[{"event_type": "Birth", "date": "1900-07-04", "year_unknown": 1}],
		)

		html = self.render(show_birthdays="1")

		birthdays = html[html.index('<div class="appendix-heading">Birthdays</div>') :]
		self.assertRegex(birthdays, r"_Test Yearless Birthday</span>\s*<span class=\"calendar-date\">July 4<")

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

	def test_booklet_fills_its_empty_pages_with_notes_pages(self):
		self.assertEqual(self.render(padding_pages="2").count('<div class="appendix-heading">Notes</div>'), 2)

		sides = self.render_pdf(booklet_printing="1")

		halves = [
			[word for x, word in get_positioned_words(side) if (x >= SHEET_WIDTH / 2) == is_right]
			for side in sides
			for is_right in (False, True)
		]
		self.assertEqual(sum(not words for words in halves), 1, "only the back cover is blank")


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


def make_group(group_name, **values):
	ensure("Group Status", {"status": "Active"})
	return frappe.get_doc({"doctype": "Group", "group_name": group_name, **values}).insert(
		ignore_permissions=True
	)


MM_TO_PX = 96 / 25.4


def make_png_data_uri(width, height):
	"""A plain PNG of *width* by *height* pixels, inline so no file is left behind."""
	output = io.BytesIO()
	Image.new("RGB", (width, height), "steelblue").save(output, "PNG")
	return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


def find_box(box, tag):
	"""The first laid-out box for an element named *tag* under *box*, or None."""
	element = getattr(box, "element", None)
	if element is not None and element.tag == tag:
		return box
	for child in getattr(box, "children", []):
		if found := find_box(child, tag):
			return found


def get_positioned_words(page):
	"""Each word on the page with the x position of the text run it is in."""
	words = []

	def visit(text, cm, tm, font, size):
		x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
		words.extend((x, word) for word in text.split())

	page.extract_text(visitor_text=visit)
	return words
