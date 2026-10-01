# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase


class TestBelief(FrappeTestCase):
	def _belief(self, title, bible_references):
		return frappe.get_doc(
			{
				"doctype": "Belief",
				"title": title,
				"belief_statement": "<p>We believe.</p>",
				"bible_references": bible_references,
			}
		).insert(ignore_permissions=True)

	def test_references_are_stored_tidied_in_the_order_typed(self):
		belief = self._belief("_Test Tidied Belief", "eph 2:8-9;rom 3:23")
		self.assertEqual(belief.bible_references, "Ephesians 2:8-9; Romans 3:23")

	def test_a_reference_nobody_can_read_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._belief("_Test Unreadable Belief", "Hezekiah 1:1")
