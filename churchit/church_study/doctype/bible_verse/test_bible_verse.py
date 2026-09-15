# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import CannotChangeConstantError
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import ensure


class TestBibleVerse(FrappeTestCase):
	def setUp(self):
		self.book = ensure(
			"Bible Book", {"book": "_Test Book"}, {"book": "_Test Book", "abbreviation": "TST"}
		)

	def _verse(self, chapter, verse):
		name = f"{self.book} {chapter}:{verse}"
		if frappe.db.exists("Bible Verse", name):
			frappe.delete_doc("Bible Verse", name, force=True, ignore_permissions=True)
		return frappe.get_doc(
			{"doctype": "Bible Verse", "book": self.book, "chapter": chapter, "verse": verse}
		).insert(ignore_permissions=True)

	def test_name_and_reference_are_built_from_book_chapter_and_verse(self):
		verse = self._verse("3", "16")
		self.assertEqual(verse.name, "_Test Book 3:16")
		self.assertEqual(verse.reference, "_Test Book 3:16")

	def test_identity_fields_are_fixed_once_saved(self):
		verse = self._verse("4", "1")
		verse.verse = "2"
		with self.assertRaises(CannotChangeConstantError):
			verse.save(ignore_permissions=True)
