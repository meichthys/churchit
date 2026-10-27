# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_website.published_fields import (
	MEMBERS,
	PUBLIC,
	SITE_WIDE_SOURCE,
	code_sources,
	fields_used_in,
	published_field_map,
	web_form_entries,
	www_routes,
)


def routes(published, doctype, fieldname):
	"""Route of every source showing *fieldname*, in the scanned map."""
	return [source["route"] for source in published.get(doctype, {}).get(fieldname, [])]


def www_directory():
	return Path(frappe.get_app_path("churchit")) / "www"


class TestPublishedFields(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_fields_read_by_a_published_web_page(self):
		frappe.get_doc(
			{
				"doctype": "Web Page",
				"title": "_Test Staff Page",
				"route": "_test-staff",
				"published": 1,
				"dynamic_template": 1,
				"content_type": "HTML",
				"main_section_html": (
					'{% set people = frappe.get_list("Person", fields=["full_name"]) %}'
					"{% for p in people %}{{ p.full_name }}{% endfor %}"
				),
			}
		).insert(ignore_permissions=True)

		published = published_field_map()
		self.assertIn(
			{"title": "_Test Staff Page", "route": "_test-staff", "access": PUBLIC},
			published["Person"]["full_name"],
		)
		self.assertNotIn("_test-staff", routes(published, "Person", "age"))

	def test_fields_read_by_get_all_and_get_value_calls(self):
		frappe.get_doc(
			{
				"doctype": "Web Page",
				"title": "_Test Sermon Page",
				"route": "_test-sermons",
				"published": 1,
				"dynamic_template": 1,
				"content_type": "HTML",
				"main_section_html": (
					'{% set sermons = frappe.get_all("Sermon", fields=["title", "series"]) %}'
					'{% for s in sermons %}{{ frappe.db.get_value("Sermon Series", s.series, "series_name") }}{% endfor %}'
				),
			}
		).insert(ignore_permissions=True)

		published = published_field_map()
		self.assertIn("_test-sermons", routes(published, "Sermon", "title"))
		self.assertIn("_test-sermons", routes(published, "Sermon Series", "series_name"))

	def test_quoted_names_count_only_inside_the_fetching_call(self):
		code = 'frappe.get_all("Function", filters={"start_date": [">=", nowdate()]}, fields=["all_day"]) "publish"'
		self.assertEqual(
			fields_used_in("Function", code) & {"all_day", "start_date", "publish"},
			{"all_day", "start_date"},
		)
		self.assertEqual(fields_used_in("Function", 'x = "all_day"'), set())

	def test_fields_read_on_every_page(self):
		published = published_field_map()
		for fieldname in ("church_name", "founding_date", "address", "abbreviation"):
			self.assertIn(SITE_WIDE_SOURCE, published["Church"].get(fieldname, []), fieldname)
		self.assertNotIn("old_parent", published["Church"])

	def test_fields_sent_by_guest_apis(self):
		sent = routes(published_field_map(), "Missionary", "geolocation")
		self.assertTrue(any(route.startswith("api/method/") for route in sent), sent)

	def test_fields_read_by_a_www_page(self):
		# www/calendar.py lists the Function fields it sends to the browser.
		self.assertIn("calendar", routes(published_field_map(), "Function", "function_name"))

	def test_fields_read_by_a_page_in_a_www_subfolder(self):
		# www/memorize/index.py is the folder's own page, at /memorize.
		self.assertIn("memorize", routes(published_field_map(), "Bible Memory Item", "progress"))
		self.assertIn("memorize/session", routes(published_field_map(), "Bible Memory Item", "progress"))

	def test_a_page_template_and_its_python_are_one_route(self):
		pages = www_routes(www_directory())
		self.assertEqual(
			{path.name for path in pages["ministry-team"]},
			{"ministry_team.py", "ministry-team.html"},
		)

	def test_fields_shown_by_a_published_web_form(self):
		published = published_field_map()
		self.assertIn("personal-details", routes(published, "Person", "photo"))
		self.assertIn("prayer-request", routes(published, "Prayer Request", "request"))

	def test_fields_read_through_an_included_template(self):
		# /statements includes the statement body, which calls the statement_header jinja method.
		published = published_field_map()
		self.assertIn("statements", routes(published, "Giving Statement", "total_amount"))
		self.assertIn("statements", routes(published, "Church", "tax_id"))

	def test_fields_read_through_an_imported_helper(self):
		# www/preferences reads each purpose and the church's name through church_communications.preferences.
		published = published_field_map()
		self.assertIn("preferences", routes(published, "Church", "church_name"))
		self.assertIn("preferences", routes(published, "Communication Purpose", "description"))

	def test_every_www_page_is_scanned(self):
		"""A page added under www/ later is scanned without touching the scanner."""
		scanned = {source["route"] for source, _ in code_sources()}
		pages = www_routes(www_directory())
		self.assertTrue(pages)
		for route in pages:
			self.assertIn(route, scanned, route)

	def test_every_published_web_form_is_scanned(self):
		"""A web form published later is scanned without touching the scanner."""
		scanned = {source["route"] for source, _, _ in web_form_entries()}
		forms = frappe.get_all(
			"Web Form", filters={"published": 1, "module": ("like", "Church%")}, pluck="route"
		)
		self.assertTrue(forms)
		for route in forms:
			self.assertIn(route, scanned, route)

	def test_a_page_that_sends_every_guest_to_login_is_members_only(self):
		access = {source["route"]: source["access"] for source, _ in code_sources()}
		self.assertEqual(access["statements"], MEMBERS)
		self.assertEqual(access["memorize"], MEMBERS)
		self.assertEqual(access["preferences"], MEMBERS)
		self.assertEqual(access["calendar"], PUBLIC)
		# /give sends guests to login only while anonymous giving is off, so it still serves them.
		self.assertEqual(access["give"], PUBLIC)

	def test_a_web_form_is_members_only_when_it_needs_a_login(self):
		access = {source["route"]: source["access"] for source, _, _ in web_form_entries()}
		self.assertEqual(access["personal-details"], MEMBERS)
		self.assertEqual(access["prayer-request-anonymous"], PUBLIC)

	def test_no_doctype_renders_itself_on_the_web(self):
		"""A web view renders a record from its own template, which nothing scans."""
		with_web_view = frappe.get_all(
			"DocType", filters={"module": ("like", "Church%"), "has_web_view": 1}, pluck="name"
		)
		self.assertEqual(
			with_web_view,
			[],
			"a doctype with a web view shows fields no source in code_sources() reads; "
			"scan its templates/ folder there before turning one on",
		)

	def test_public_pages_read_records_through_scannable_apis(self):
		"""The badge is read off the page's own code, so the page must read records in the open."""
		sources = list(code_sources())
		self.assertTrue(sources)
		for source, code in sources:
			for unscannable in ("frappe.qb", "frappe.db.sql"):
				self.assertNotIn(
					unscannable,
					code,
					f"{source['route']} reads records with {unscannable}, which the published-field "
					"scanner cannot follow; use frappe.get_all/get_list or extend it",
				)

	def test_my_household_and_the_member_directory_are_members_only(self):
		access = {source["route"]: source["access"] for source, _ in code_sources()}
		self.assertEqual(access["household"], MEMBERS)
		self.assertEqual(access["directory"], MEMBERS)

	def test_fields_shown_on_a_song_slide(self):
		published = published_field_map()
		for doctype, fieldname in (
			("Song", "title"),
			("Song", "copyright"),
			("Song", "ccli"),
			("Slide", "content"),
			("Slide", "background_image"),
			("Church", "ccli_license_number"),
		):
			self.assertIn(
				{"title": "Sermon Presentation", "route": "sermon-presentation", "access": PUBLIC},
				published[doctype][fieldname],
				(doctype, fieldname),
			)
		for fieldname in ("arrangements", "media"):
			self.assertNotIn("sermon-presentation", routes(published, "Song", fieldname), fieldname)

	def test_fields_shown_on_my_household(self):
		published = published_field_map()
		for doctype, fieldname in (
			("Family", "family_name"),
			("Family", "photo"),
			("Person", "display_name"),
			("Person", "age"),
			("Address", "address_line1"),
			("Address", "city"),
		):
			self.assertIn("household", routes(published, doctype, fieldname), (doctype, fieldname))

	def test_fields_shown_in_the_member_directory(self):
		published = published_field_map()
		for doctype, fieldname in (
			("Person", "first_name"),
			("Person", "nickname"),
			("Person", "last_name"),
			("Person", "photo"),
			("Person", "birth_month"),
			("Person", "birth_day"),
			("Family", "photo"),
			("Email Address", "email_address"),
			("Phone Number", "phone_number"),
			("Address", "address_line1"),
			("Address", "city"),
		):
			self.assertIn("directory", routes(published, doctype, fieldname), (doctype, fieldname))

	def test_the_birthday_and_directory_choices_show_on_personal_details(self):
		published = published_field_map()
		for fieldname in ("birthday", "hide_from_directory", "share_email", "share_birthday"):
			self.assertIn("personal-details", routes(published, "Person", fieldname), fieldname)

	def test_a_key_only_web_form_shows_its_record_to_the_link_holder_only(self):
		from churchit.church_website.published_fields import LINK_HOLDERS, web_form_access

		access = {source["route"]: source["access"] for source, _, _ in web_form_entries()}
		self.assertEqual(access["update-your-details"], LINK_HOLDERS)
		self.assertEqual(web_form_access(frappe._dict(login_required=1, key_required=1)), MEMBERS)
		self.assertIn("update-your-details", routes(published_field_map(), "Person", "alergies"))
