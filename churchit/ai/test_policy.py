# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The starter "How We Use AI" page is unpublished, made once, and the church's to edit."""

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.ai.policy import PAGE_NAME, create_how_we_use_ai_page


class TestHowWeUseAiPage(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Web Page", {"name": PAGE_NAME})

	def test_page_is_made_unpublished(self):
		create_how_we_use_ai_page()

		page = frappe.get_doc("Web Page", PAGE_NAME)
		self.assertEqual(page.published, 0)
		self.assertIn("AI", page.main_section_html)

	def test_a_church_edit_survives_a_second_run(self):
		create_how_we_use_ai_page()
		frappe.db.set_value("Web Page", PAGE_NAME, {"main_section_html": "Our words", "published": 1})

		create_how_we_use_ai_page()

		page = frappe.get_doc("Web Page", PAGE_NAME)
		self.assertEqual(page.main_section_html, "Our words")
		self.assertEqual(page.published, 1)
