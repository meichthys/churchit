# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import ensure


class TestBibleReference(FrappeTestCase):
	def setUp(self):
		self.book = ensure(
			"Bible Book", {"book": "_Test Ref Book"}, {"book": "_Test Ref Book", "abbreviation": "TRB"}
		)
		self.translation = ensure(
			"Bible Translation",
			{"translation": "_Test Translation"},
			{"translation": "_Test Translation", "abbreviation": "TT"},
		)
		self.start = self._verse(1, 1)
		self.end = self._verse(1, 3)

	def _verse(self, chapter, verse):
		return ensure(
			"Bible Verse",
			{"name": f"{self.book} {chapter}:{verse}"},
			{"book": self.book, "chapter": chapter, "verse": verse},
		)

	def _reference(self, **values):
		for name in frappe.get_all(
			"Bible Reference", filters={"start_verse": ["like", f"{self.book}%"]}, pluck="name"
		):
			frappe.delete_doc("Bible Reference", name, force=True, ignore_permissions=True)
		return frappe.get_doc({"doctype": "Bible Reference", **values}).insert(ignore_permissions=True)

	def test_single_verse_reference(self):
		reference = self._reference(start_verse=self.start)
		self.assertEqual(reference.name, "_Test Ref Book 1:1")
		self.assertEqual(reference.reference, "_Test Ref Book 1:1")

	def test_range_with_translation(self):
		reference = self._reference(start_verse=self.start, end_verse=self.end, translation=self.translation)
		self.assertEqual(reference.name, "_Test Ref Book 1:1 - _Test Ref Book 1:3 (TT)")
		self.assertEqual(reference.reference, "_Test Ref Book 1:1 - _Test Ref Book 1:3 (TT)")

	def test_same_start_and_end_collapses_to_one_verse(self):
		reference = self._reference(start_verse=self.start, end_verse=self.start)
		self.assertEqual(reference.reference, "_Test Ref Book 1:1")

	def test_start_verse_is_required(self):
		with self.assertRaises(ValidationError):
			self._reference(end_verse=self.end)

	def test_changing_the_range_renames_the_record(self):
		reference = self._reference(start_verse=self.start)
		reference.end_verse = self.end
		reference.save(ignore_permissions=True)

		self.assertTrue(frappe.db.exists("Bible Reference", "_Test Ref Book 1:1 - _Test Ref Book 1:3"))
		self.assertFalse(frappe.db.exists("Bible Reference", "_Test Ref Book 1:1"))
