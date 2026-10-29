# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from unittest.mock import patch

import frappe
from frappe.exceptions import PermissionError, ValidationError
from frappe.handler import execute_cmd, run_doc_method
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.church_access import set_user_church
from churchit.church_study.doctype.bible_memory_item.bible_memory_item import (
	BibleMemoryItem,
	assign_memory,
	complete_session,
	record_mistake,
)
from churchit.tests.helpers import ensure_user, make_person, make_translation, make_two_churches

REFERENCE = "John 1:1"
MODULE = "churchit.church_study.doctype.bible_memory_item.bible_memory_item"


def as_get():
	"""A GET, which another site can start with the session cookie and Frappe checks for no CSRF token."""
	return patch.object(frappe.local, "request", frappe._dict(method="GET"), create=True)


class TestBibleMemoryItem(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.translation = make_translation(cls, "_TMB", [("JHN", 1, 1, "In the beginning was the Word.")])
		cls.user = ensure_user("_test_memorizer@example.com", "_Test Memorizer")
		cls.other_user = ensure_user("_test_other_memorizer@example.com", "_Test Other Memorizer")

	def setUp(self):
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

	def test_practice_takes_a_post(self):
		item = self._item(progress=10)
		attempts = {"record_mistake": {"word_index": 0}, "complete_session": {"mode": "blur"}}

		with as_get():
			for method, args in attempts.items():
				with (
					patch.object(frappe.local, "form_dict", frappe._dict(name=item.name, **args)),
					self.assertRaises(PermissionError, msg=method),
				):
					execute_cmd(f"{MODULE}.{method}")
				with self.assertRaises(PermissionError, msg=f"BibleMemoryItem.{method}"):
					run_doc_method(method, dt=item.doctype, dn=item.name, args=frappe.as_json(args))

		self.assertEqual(frappe.db.get_value("Bible Memory Item", item.name, "progress"), 10)

	def test_parse_indices_tolerates_bad_input(self):
		parse = BibleMemoryItem._parse_indices
		self.assertEqual(parse(None), [])
		self.assertEqual(parse(""), [])
		self.assertEqual(parse("not json"), [])
		self.assertEqual(parse('{"a": 1}'), [])
		self.assertEqual(parse('[1, "2", "x", null]'), [1, 2])
		self.assertEqual(parse([3, "4"]), [3, 4])


class TestAssignMemory(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.translation = make_translation(cls, "_TAM", [("PSA", 23, 1, "The LORD is my shepherd.")])
		cls.learner = ensure_user("_test_learner@example.com", "_Test Learner")
		cls.linked = make_person("_Test Assign", "Linked", user=cls.learner).name
		cls.unlinked = make_person("_Test Assign", "Unlinked").name

	def setUp(self):
		frappe.db.delete("Bible Memory Item", {"translation": self.translation})

	def tearDown(self):
		frappe.set_user("Administrator")

	def _items(self):
		return frappe.get_all(
			"Bible Memory Item",
			filters={"translation": self.translation},
			fields=["user", "bible_reference", "assigned_by", "group"],
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

	def test_a_group_assignment_files_its_members_items_under_the_group(self):
		other = ensure_user("_test_named_learner@example.com", "_Test Named Learner")
		make_person("_Test Assign", "Named", user=other)
		group = self._group("_Test Stored Memory Group", self.linked)
		assign_memory("Psalms 23:1", self.translation, users=[other], group=group)
		self.assertEqual(
			{item.user: item.group for item in self._items()}, {self.learner: group, other: None}
		)

	def test_a_held_passage_keeps_its_group(self):
		assign_memory("Psalms 23:1", self.translation, users=[self.learner])
		group = self._group("_Test Later Memory Group", self.linked)
		self.assertEqual(assign_memory("Psalms 23:1", self.translation, group=group)["skipped"], 1)
		self.assertEqual([item.group for item in self._items()], [None])

	def test_only_assign_memory_sets_the_group(self):
		group = self._group("_Test Hand Memory Group", self.linked)
		frappe.set_user(self.learner)
		item = {
			"doctype": "Bible Memory Item",
			"bible_reference": "Psalms 23:1",
			"translation": self.translation,
		}
		with self.assertRaises(PermissionError):
			frappe.get_doc({**item, "group": group}).insert()

		mine = frappe.get_doc(item).insert()
		mine.group = group
		with self.assertRaises(PermissionError):
			mine.save()

	def test_deleting_a_group_clears_it_from_the_items(self):
		group = self._group("_Test Deleted Memory Group", self.linked)
		assign_memory("Psalms 23:1", self.translation, group=group)
		frappe.delete_doc("Group", group)
		self.assertEqual([(item.user, item.group) for item in self._items()], [(self.learner, None)])

	def test_a_duplicated_item_drops_the_group(self):
		other = ensure_user("_test_copy_learner@example.com", "_Test Copy Learner")
		make_person("_Test Assign", "Copy", user=other)
		group = self._group("_Test Copied Memory Group", self.linked)
		assign_memory("Psalms 23:1", self.translation, group=group)
		item = frappe.get_doc("Bible Memory Item", {"translation": self.translation})

		copy = frappe.copy_doc(item, ignore_no_copy=False)
		copy.user = other
		self.assertIsNone(copy.group)
		copy.insert()

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

	def test_assigning_takes_a_post(self):
		form = frappe._dict(reference="Psalms 23:1", translation=self.translation, users=self.learner)
		with (
			as_get(),
			patch.object(frappe.local, "form_dict", form),
			self.assertRaises(PermissionError),
		):
			execute_cmd(f"{MODULE}.assign_memory")

		self.assertEqual(self._items(), [])

	def test_assign_refuses_a_user_of_another_church(self):
		_root, branch_a, branch_b = make_two_churches()
		self.addCleanup(frappe.clear_cache)
		frappe.db.set_value("Person", self.linked, "church", branch_a)
		manager_b = ensure_user("_test_memory_manager_b@example.com", "Manager B", roles=("Church Manager",))
		set_user_church(manager_b, branch_b)
		no_person = ensure_user("_test_memory_no_person@example.com", "No Person")

		frappe.set_user(manager_b)
		for user in (self.learner, no_person):
			with self.assertRaises(PermissionError):
				assign_memory("Psalms 23:1", self.translation, users=[user])
		self.assertEqual(self._items(), [])

		frappe.db.set_value("Person", self.linked, "church", branch_b)
		self.assertEqual(assign_memory("Psalms 23:1", self.translation, users=[self.learner])["created"], 1)

	def test_assign_refuses_an_unreadable_translation(self):
		frappe.db.set_value("Bible Translation", self.translation, "status", "Downloading")
		self.addCleanup(frappe.db.set_value, "Bible Translation", self.translation, "status", "Ready")
		with self.assertRaises(PermissionError):
			assign_memory("Psalms 23:1", self.translation, users=[self.learner])
		self.assertEqual(self._items(), [])

	def test_a_desk_save_gets_the_same_checks(self):
		_root, branch_a, branch_b = make_two_churches()
		self.addCleanup(frappe.clear_cache)
		frappe.db.set_value("Person", self.linked, "church", branch_a)
		manager_b = ensure_user("_test_memory_manager_b@example.com", "Manager B", roles=("Church Manager",))
		set_user_church(manager_b, branch_b)
		other = ensure_user("_test_other_learner@example.com", "_Test Other Learner")

		def insert(session_user, **values):
			frappe.set_user(session_user)
			item = {"doctype": "Bible Memory Item", "bible_reference": "Psalms 23:1"}
			return frappe.get_doc({**item, "translation": self.translation, **values}).insert()

		for user, values in ((manager_b, {"user": self.learner}), (other, {"user": self.learner})):
			with self.assertRaises(PermissionError):
				insert(user, **values)
		self.assertEqual(self._items(), [])

		frappe.db.set_value("Bible Translation", self.translation, "status", "Downloading")
		self.addCleanup(frappe.db.set_value, "Bible Translation", self.translation, "status", "Ready")
		with self.assertRaises(PermissionError):
			insert(self.learner)
		frappe.db.set_value("Bible Translation", self.translation, "status", "Ready")
		self.assertEqual(insert(self.learner).user, self.learner)

	def test_non_manager_cannot_list_a_groups_members(self):
		group = self._group("_Test Private Memory Group", self.unlinked)
		frappe.set_user(self.learner)
		# The unlinked-members error names everyone in the group.
		with self.assertRaises(PermissionError):
			assign_memory("Psalms 23:1", self.translation, group=group)
