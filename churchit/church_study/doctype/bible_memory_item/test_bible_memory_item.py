# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.exceptions import PermissionError, ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_study.doctype.bible_memory_item.bible_memory_item import (
	BibleMemoryItem,
	complete_session,
	record_mistake,
)
from churchit.tests.helpers import ensure, ensure_user


class TestBibleMemoryItem(FrappeTestCase):
	def setUp(self):
		book = ensure("Bible Book", {"book": "_Test Memory Book"}, {"book": "_Test Memory Book", "abbreviation": "TMB"})
		verse = ensure(
			"Bible Verse", {"name": f"{book} 1:1"}, {"book": book, "chapter": 1, "verse": 1}
		)
		self.reference = ensure(
			"Bible Reference", {"start_verse": verse, "end_verse": ["is", "not set"]}, {"start_verse": verse}
		)
		self.user = ensure_user("_test_memorizer@example.com", "_Test Memorizer")
		self.other_user = ensure_user("_test_other_memorizer@example.com", "_Test Other Memorizer")
		frappe.db.delete("Bible Memory Item", {"bible_reference": self.reference})
		frappe.set_user(self.user)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _item(self, **values):
		return frappe.get_doc(
			{"doctype": "Bible Memory Item", "bible_reference": self.reference, **values}
		).insert(ignore_permissions=True)

	def test_user_defaults_to_the_session_user(self):
		self.assertEqual(self._item().user, self.user)

	def test_same_passage_cannot_be_added_twice_for_one_user(self):
		self._item()
		with self.assertRaises(ValidationError):
			self._item()

	def test_memorized_flag_is_dropped_when_progress_falls(self):
		item = self._item(progress=100, memorized=1, memorized_on="2030-01-01")
		self.assertTrue(item.memorized)

		item.progress = 90
		item.save(ignore_permissions=True)
		self.assertFalse(item.memorized)
		self.assertIsNone(item.memorized_on)

	def test_record_mistake_tallies_the_word_and_costs_progress(self):
		item = self._item(progress=10)
		item.record_mistake(3)
		result = item.record_mistake("3")

		self.assertEqual(result, {"progress": 6, "word_mistakes": {"3": 2}})
		self.assertEqual(json.loads(item.word_mistakes), {"3": 2})

	def test_record_mistake_never_goes_below_zero(self):
		item = self._item(progress=1)
		self.assertEqual(item.record_mistake(0)["progress"], 0)

	def test_blur_session_adds_five_but_stops_short_of_memorized(self):
		item = self._item(progress=96)
		result = item.complete_session("blur")
		self.assertEqual(result["progress"], 99)
		self.assertEqual(result["bonus"], 5)
		self.assertFalse(result["memorized"])

	def test_perfect_type_session_memorizes_and_counts(self):
		item = self._item(progress=60, word_mistakes=json.dumps({"2": 1, "5": 2}))
		result = item.complete_session("type", mistakes=0, correct_word_indices="[2, 5]")

		self.assertEqual(result["progress"], 100)
		self.assertEqual(result["bonus"], 50)
		self.assertTrue(result["memorized"])
		self.assertIsNotNone(result["memorized_on"])
		self.assertEqual(result["times_memorized"], 1)
		# Getting a word right forgives one earlier mistake on it.
		self.assertEqual(result["word_mistakes"], {"5": 1})

	def test_type_session_bonus_depends_on_mistakes(self):
		item = self._item(progress=0)
		self.assertEqual(item.complete_session("type", mistakes=2)["bonus"], 10)
		self.assertEqual(item.complete_session("type", mistakes=3)["bonus"], 0)
		self.assertEqual(item.times_memorized, 0)

	def test_sessions_are_logged_and_deleted_with_the_item(self):
		item = self._item()
		item.complete_session("type", mistakes=1)
		item.complete_session("blur")

		sessions = frappe.get_all(
			"Memory Session", filters={"bible_memory_item": item.name}, fields=["mode", "mistakes", "progress_delta"]
		)
		self.assertEqual(
			sorted((s.mode, s.mistakes, s.progress_delta) for s in sessions),
			[("Blur", 0, 5), ("Type", 1, 10)],
		)

		item.delete()
		self.assertFalse(frappe.db.exists("Memory Session", {"bible_memory_item": item.name}))

	def test_invalid_mode_is_rejected(self):
		with self.assertRaises(ValidationError):
			self._item().complete_session("listen")

	def test_only_the_owner_can_practise(self):
		item = self._item()
		frappe.set_user(self.other_user)
		with self.assertRaises(PermissionError):
			record_mistake(item.name, 0)
		with self.assertRaises(PermissionError):
			complete_session(item.name, "blur")

	def test_parse_indices_tolerates_bad_input(self):
		parse = BibleMemoryItem._parse_indices
		self.assertEqual(parse(None), [])
		self.assertEqual(parse(""), [])
		self.assertEqual(parse("not json"), [])
		self.assertEqual(parse('{"a": 1}'), [])
		self.assertEqual(parse("[1, \"2\", \"x\", null]"), [1, 2])
		self.assertEqual(parse([3, "4"]), [3, 4])
