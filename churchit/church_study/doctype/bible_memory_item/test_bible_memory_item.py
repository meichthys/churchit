# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.exceptions import PermissionError, ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_study.doctype.bible_memory_item.bible_memory_item import (
	BibleMemoryItem,
	assign_memory,
	complete_session,
	record_mistake,
)
from churchit.tests.helpers import ensure_user, make_person, make_translation

REFERENCE = "John 1:1"


class TestBibleMemoryItem(FrappeTestCase):
	def setUp(self):
		self.translation = make_translation(self, "_TMB", [("JHN", 1, 1, "In the beginning was the Word.")])
		self.user = ensure_user("_test_memorizer@example.com", "_Test Memorizer")
		self.other_user = ensure_user("_test_other_memorizer@example.com", "_Test Other Memorizer")
		frappe.db.delete("Bible Memory Item", {"bible_reference": REFERENCE})
		frappe.set_user(self.user)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _item(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Bible Memory Item",
				"bible_reference": REFERENCE,
				"translation": self.translation,
				**values,
			}
		).insert(ignore_permissions=True)

	def test_user_defaults_to_the_session_user(self):
		self.assertEqual(self._item().user, self.user)

	def test_the_reference_is_stored_tidied(self):
		self.assertEqual(self._item(bible_reference="jn 1:1").bible_reference, REFERENCE)

	def test_same_passage_cannot_be_added_twice_for_one_user(self):
		self._item()
		with self.assertRaises(ValidationError):
			self._item(bible_reference="jn 1:1")

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
			"Memory Session",
			filters={"bible_memory_item": item.name},
			fields=["mode", "mistakes", "progress_delta"],
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
		self.assertEqual(parse('[1, "2", "x", null]'), [1, 2])
		self.assertEqual(parse([3, "4"]), [3, 4])


class TestAssignMemory(FrappeTestCase):
	def setUp(self):
		self.translation = make_translation(self, "_TAM", [("PSA", 23, 1, "The LORD is my shepherd.")])
		self.learner = ensure_user("_test_learner@example.com", "_Test Learner")
		self.linked = make_person("_Test Assign", "Linked", user=self.learner).name
		self.unlinked = make_person("_Test Assign", "Unlinked").name
		frappe.db.delete("Bible Memory Item", {"translation": self.translation})

	def tearDown(self):
		frappe.set_user("Administrator")

	def _items(self):
		return frappe.get_all(
			"Bible Memory Item",
			filters={"translation": self.translation},
			fields=["user", "bible_reference", "assigned_by"],
		)

	def _group(self, name, *people):
		group = frappe.get_doc({"doctype": "Group", "group_name": name})
		for person in people:
			group.append("members", {"person": person})
		return group.insert(ignore_permissions=True).name

	def test_assigns_the_tidied_passage_to_each_user_once(self):
		result = assign_memory("ps 23:1", self.translation, users=self.learner)
		self.assertEqual(result, {"created": 1, "skipped": 0, "missing_users": []})
		self.assertEqual(
			[(i.user, i.bible_reference, i.assigned_by) for i in self._items()],
			[(self.learner, "Psalms 23:1", "Administrator")],
		)
		self.assertEqual(assign_memory("Psalms 23:1", self.translation, users=[self.learner])["skipped"], 1)

	def test_group_expands_to_members_with_portal_users(self):
		group = self._group("_Test Memory Group", self.linked, self.unlinked)
		result = assign_memory("Psalms 23:1", self.translation, group=group)
		self.assertEqual(result["created"], 1)
		self.assertEqual(len(result["missing_users"]), 1)
		self.assertIn(self.unlinked, result["missing_users"][0])

	def test_a_user_named_twice_is_assigned_once(self):
		group = self._group("_Test Overlap Group", self.linked)
		result = assign_memory("Psalms 23:1", self.translation, users=json.dumps([self.learner]), group=group)
		self.assertEqual((result["created"], result["skipped"]), (1, 0))

	def test_group_without_portal_users_is_reported(self):
		group = self._group("_Test Unlinked Group", self.unlinked)
		with self.assertRaises(ValidationError):
			assign_memory("Psalms 23:1", self.translation, group=group)

	def test_requires_someone_to_assign_to(self):
		with self.assertRaises(ValidationError):
			assign_memory("Psalms 23:1", self.translation)

	def test_only_managers_can_assign(self):
		frappe.set_user(self.learner)
		with self.assertRaises(PermissionError):
			assign_memory("Psalms 23:1", self.translation, users=[self.learner])

	def test_non_manager_cannot_list_a_groups_members(self):
		group = self._group("_Test Private Memory Group", self.unlinked)
		frappe.set_user(self.learner)
		# The unlinked-members error names everyone in the group.
		with self.assertRaises(PermissionError):
			assign_memory("Psalms 23:1", self.translation, group=group)
