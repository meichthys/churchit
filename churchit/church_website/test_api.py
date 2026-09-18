# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import PermissionError
from frappe.tests.utils import FrappeTestCase

from churchit.church_website.api import (
	SITE_WIDE_SOURCE,
	fields_used_in,
	get_church_doctypes,
	get_published_fields,
	get_published_web_page,
	search_church_recipient,
)
from churchit.tests.helpers import ensure_user, make_person


class TestWebsiteApi(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_published_fields_found_in_dynamic_web_pages(self):
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

		fields = get_published_fields("Person")
		self.assertIn({"title": "_Test Staff Page", "route": "_test-staff"}, fields.get("full_name", []))
		self.assertNotIn("_test-staff", [s["route"] for s in fields.get("age", [])])

	def test_published_fields_found_in_get_all_and_get_value_calls(self):
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

		self.assertIn("_test-sermons", [s["route"] for s in get_published_fields("Sermon").get("title", [])])
		self.assertIn(
			"_test-sermons",
			[s["route"] for s in get_published_fields("Sermon Series").get("series_name", [])],
		)

	def test_quoted_names_count_only_inside_the_fetching_call(self):
		code = 'frappe.get_all("Function", filters={"start_date": [">=", nowdate()]}, fields=["all_day"]) "title"'
		self.assertEqual(
			fields_used_in("Function", {"all_day", "title", "start_date"}, code), {"all_day", "start_date"}
		)
		self.assertEqual(fields_used_in("Function", {"all_day"}, 'x = "all_day"'), set())

	def test_church_fields_read_on_every_page_are_published(self):
		fields = get_published_fields("Church")
		for fieldname in ("church_name", "founding_date", "address", "abbreviation"):
			self.assertIn(SITE_WIDE_SOURCE, fields.get(fieldname, []), fieldname)
		self.assertNotIn("tax_id", fields)

	def test_fields_sent_by_guest_apis_are_published(self):
		routes = [s["route"] for s in get_published_fields("Missionary").get("geolocation", [])]
		self.assertTrue(any(route.startswith("api/method/") for route in routes), routes)

	def test_published_fields_found_in_www_routes(self):
		# www/calendar.py lists the Function fields it sends to the browser.
		fields = get_published_fields("Function")
		self.assertIn("calendar", [s["route"] for s in fields.get("function_name", [])])

	def test_published_fields_is_restricted_to_managers(self):
		frappe.set_user(ensure_user("_test_church_user@example.com", "_Test Church User"))
		with self.assertRaises(PermissionError):
			get_published_fields("Person")

	def test_published_web_page_is_found_by_its_navbar_url(self):
		frappe.get_doc(
			{"doctype": "Web Page", "title": "_Test Linked Page", "route": "_test-linked", "published": 1}
		).insert(ignore_permissions=True)

		page = get_published_web_page("/_test-linked")
		self.assertEqual(page.title, "_Test Linked Page")
		self.assertEqual(get_published_web_page("/_test-linked?utm=x#top").name, page.name)

	def test_unpublished_www_and_external_links_have_no_page(self):
		frappe.get_doc(
			{"doctype": "Web Page", "title": "_Test Hidden Page", "route": "_test-hidden", "published": 0}
		).insert(ignore_permissions=True)

		self.assertIsNone(get_published_web_page("/_test-hidden"))
		self.assertIsNone(get_published_web_page("/calendar"))
		self.assertIsNone(get_published_web_page("https://example.com/_test-linked"))
		self.assertIsNone(get_published_web_page("/"))
		self.assertIsNone(get_published_web_page(""))

	def test_published_web_page_lookup_is_restricted_to_managers(self):
		frappe.set_user(ensure_user("_test_church_user@example.com", "_Test Church User"))
		with self.assertRaises(PermissionError):
			get_published_web_page("/home")

	def test_church_doctypes_are_non_child_church_module_doctypes(self):
		names = [row.name for row in get_church_doctypes()]
		self.assertIn("Person", names)
		self.assertIn("Function", names)
		self.assertNotIn("Group Member", names)
		self.assertNotIn("User", names)
		self.assertEqual(names, sorted(names))

	def test_recipient_search_matches_on_title(self):
		person = make_person("_Test Searchable", "Recipient")
		results = search_church_recipient("Person", "_Test Searchable")
		self.assertIn({"name": person.name, "label": "_Test Searchable Recipient"}, results)

	def test_recipient_search_rejects_non_church_doctypes(self):
		with self.assertRaises(PermissionError):
			search_church_recipient("User", "admin")
