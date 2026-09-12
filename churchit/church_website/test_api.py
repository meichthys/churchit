# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import PermissionError
from frappe.tests.utils import FrappeTestCase

from churchit.church_website.api import (
	get_church_doctypes,
	get_published_fields,
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

	def test_published_fields_found_in_www_routes(self):
		# www/calendar.py lists the Function fields it sends to the browser.
		fields = get_published_fields("Function")
		self.assertIn("calendar", [s["route"] for s in fields.get("function_name", [])])

	def test_published_fields_is_restricted_to_managers(self):
		frappe.set_user(ensure_user("_test_church_user@example.com", "_Test Church User"))
		with self.assertRaises(PermissionError):
			get_published_fields("Person")

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
