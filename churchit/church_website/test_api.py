# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import PermissionError
from frappe.tests.utils import FrappeTestCase

from churchit.church_website.api import (
	get_published_fields,
	get_published_web_page,
	get_recipient_doctypes,
	get_website_home_page,
	search_church_recipient,
)
from churchit.tests.helpers import ensure_user, make_person


class TestWebsiteApi(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_published_fields_answers_the_whole_map_or_one_doctype(self):
		self.assertIn("Person", get_published_fields())
		# A browser running a cached copy of the badge script asks for one doctype.
		self.assertEqual(get_published_fields("Person"), get_published_fields()["Person"])
		self.assertEqual(get_published_fields("_Not A Doctype"), {})

	def test_any_desk_user_gets_the_website_home_page(self):
		home_page = frappe.db.get_single_value("Website Settings", "home_page")
		frappe.set_user(
			ensure_user("_test_home_page_staff@example.com", "_Test Staff", roles=("Church Staff",))
		)
		self.assertEqual(get_website_home_page(), home_page or "login")

	def test_published_fields_is_restricted_to_managers(self):
		frappe.set_user(ensure_user("_test_church_user@example.com", "_Test Church User"))
		with self.assertRaises(PermissionError):
			get_published_fields()

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

	def test_recipient_doctypes_are_the_ones_a_request_may_name(self):
		names = [row["name"] for row in get_recipient_doctypes()]
		self.assertEqual(names, ["Person", "Family", "Group", "Ministry", "Missionary"])

	def test_recipient_search_matches_on_title(self):
		person = make_person("_Test Searchable", "Recipient")
		results = search_church_recipient("Person", "_Test Searchable")
		self.assertIn({"name": person.name, "label": "_Test Searchable Recipient"}, results)

	def test_recipient_search_rejects_other_doctypes(self):
		for doctype in ("User", "Counseling Case"):
			with self.assertRaises(PermissionError):
				search_church_recipient(doctype, "admin")
