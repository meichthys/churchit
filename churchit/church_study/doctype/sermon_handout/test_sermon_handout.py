# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.handler import execute_cmd
from frappe.tests.utils import FrappeTestCase

from churchit.church_study.doctype.sermon_handout.sermon_handout import fillable_content, make_handout


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

	def test_bracketed_phrases_become_inputs_without_the_answers(self):
		fillable = fillable_content("<p>By [grace] through [faith in Christ], not [works].</p>")
		self.assertEqual(fillable.count("<input"), 3)
		self.assertIn('data-blank="3"', fillable)
		for answer in ("grace", "faith in Christ", "works"):
			self.assertNotIn(answer, fillable)
		self.assertIn("not ", fillable)

	def test_make_handout_copies_the_sermon_notes_and_links_back(self):
		sermon = frappe.get_doc(
			{"doctype": "Sermon", "title": "_Test Handout Sermon", "notes": "<p>Point one: [love]</p>"}
		).insert(ignore_permissions=True)

		name = make_handout(sermon.name)

		handout = frappe.get_doc("Sermon Handout", name)
		self.assertEqual(handout.title, "_Test Handout Sermon")
		self.assertEqual(handout.content, "<p>Point one: [love]</p>")
		self.assertEqual(frappe.db.get_value("Sermon", sermon.name, "handout"), name)

	def test_making_a_handout_takes_a_post(self):
		"""Frappe checks the CSRF token only on a POST, and a GET from another site carries the session."""
		sermon = frappe.get_doc(
			{"doctype": "Sermon", "title": "_Test Get Sermon", "notes": "<p>[grace]</p>"}
		).insert(ignore_permissions=True)

		with (
			patch.object(frappe.local, "request", frappe._dict(method="GET"), create=True),
			patch.object(frappe.local, "form_dict", frappe._dict(sermon=sermon.name)),
			self.assertRaises(frappe.PermissionError),
		):
			execute_cmd("churchit.church_study.doctype.sermon_handout.sermon_handout.make_handout")

		self.assertFalse(frappe.db.get_value("Sermon", sermon.name, "handout"))
