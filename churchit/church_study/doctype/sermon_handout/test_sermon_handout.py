# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_study.doctype.sermon_handout.sermon_handout import make_handout


class TestSermonHandout(FrappeTestCase):
	def test_bracketed_phrases_print_as_blanks(self):
		handout = frappe.get_doc(
			{
				"doctype": "Sermon Handout",
				"title": "_Test Handout",
				"content": "<p>By [grace] you have been saved through [faith in Christ].</p>",
			}
		).insert(ignore_permissions=True)

		rendered = handout.rendered_content
		self.assertNotIn("grace", rendered)
		self.assertNotIn("faith in Christ", rendered)
		self.assertEqual(rendered.count('class="blank"'), 2)
		self.assertIn("min-width:12em", rendered)

	def test_make_handout_copies_the_sermon_notes_and_links_back(self):
		sermon = frappe.get_doc(
			{"doctype": "Sermon", "title": "_Test Handout Sermon", "notes": "<p>Point one: [love]</p>"}
		).insert(ignore_permissions=True)

		name = make_handout(sermon.name)

		handout = frappe.get_doc("Sermon Handout", name)
		self.assertEqual(handout.title, "_Test Handout Sermon")
		self.assertEqual(handout.content, "<p>Point one: [love]</p>")
		self.assertEqual(frappe.db.get_value("Sermon", sermon.name, "handout"), name)
