# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.exceptions import PermissionError, ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_study import bible_api
from churchit.church_study.bible_api import (
	_flatten_verse_content,
	assign_memory,
	fetch_reference_text,
	get_chapters_for_book,
	get_or_create_reference,
	get_verses_for_chapter,
)
from churchit.tests.helpers import ensure, ensure_user, make_person

BOOK = "_Test Api Book"
TRANSLATION = "_Test Api Translation"


def fake_helloao(url):
	"""Stand-in for bible.helloao.org, keyed on the URL suffix."""
	if url.endswith("available_translations.json"):
		return {"translations": [{"id": "TAT", "shortName": "TAT", "language": "eng"}]}
	if url.endswith("books.json"):
		return {"books": [{"id": "TAB", "shortName": "TAB", "numberOfChapters": 2}]}
	chapter = int(url.rsplit("/", 1)[-1].removesuffix(".json"))
	return {
		"chapter": {
			"content": [
				{"type": "heading", "content": ["Ignored"]},
				{"type": "verse", "number": 1, "content": [f"Chapter {chapter} verse one"]},
				{"type": "verse", "number": 2, "content": [{"text": "verse"}, " two"]},
				{"type": "verse", "number": 3, "content": ["verse three"]},
			]
		}
	}


class TestBibleApi(FrappeTestCase):
	def setUp(self):
		self.book = ensure("Bible Book", {"book": BOOK}, {"book": BOOK, "abbreviation": "TAB"})
		self.translation = ensure(
			"Bible Translation",
			{"translation": TRANSLATION},
			{"translation": TRANSLATION, "abbreviation": "TAT"},
		)
		frappe.db.delete("Bible Reference", {"start_verse": ["like", f"{BOOK}%"]})
		patcher = patch.object(bible_api, "_http_get_json", side_effect=fake_helloao)
		self.http = patcher.start()
		self.addCleanup(patcher.stop)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_flatten_verse_content_joins_strings_and_text_nodes(self):
		self.assertEqual(
			_flatten_verse_content(["For God ", {"text": "so"}, {"noteId": 1}, " loved"]), "For God so loved"
		)
		self.assertEqual(_flatten_verse_content("  plain text "), "plain text")
		self.assertEqual(_flatten_verse_content(None), "")

	def test_chapters_and_verses_come_from_the_translation_metadata(self):
		self.assertEqual(get_chapters_for_book(self.book, self.translation), [1, 2])
		self.assertEqual(get_verses_for_chapter(self.book, 1, self.translation), [1, 2, 3])

	def test_unavailable_translation_is_reported(self):
		missing = ensure(
			"Bible Translation",
			{"translation": "_Test Missing"},
			{"translation": "_Test Missing", "abbreviation": "NOPE"},
		)
		with self.assertRaises(ValidationError):
			get_chapters_for_book(self.book, missing)

	def test_get_or_create_reference_creates_verses_and_fetches_text(self):
		name = get_or_create_reference(self.book, 1, 2, 3, self.translation)

		reference = frappe.get_doc("Bible Reference", name)
		self.assertEqual(reference.start_verse, f"{BOOK} 1:2")
		self.assertEqual(reference.end_verse, f"{BOOK} 1:3")
		self.assertEqual(reference.reference_text, "2. verse two 3. verse three")
		# Asking again reuses the record and skips the network.
		calls = self.http.call_count
		self.assertEqual(get_or_create_reference(self.book, 1, 2, 3, self.translation), name)
		self.assertEqual(self.http.call_count, calls)

	def test_get_or_create_reference_collapses_single_verse_ranges(self):
		name = get_or_create_reference(self.book, 1, 1, 1, self.translation)
		self.assertIsNone(frappe.db.get_value("Bible Reference", name, "end_verse"))
		self.assertEqual(
			frappe.db.get_value("Bible Reference", name, "reference_text"), "1. Chapter 1 verse one"
		)

	def test_get_or_create_reference_validates_its_input(self):
		with self.assertRaises(ValidationError):
			get_or_create_reference(self.book, 1, 3, 2, self.translation)
		with self.assertRaises(ValidationError):
			get_or_create_reference(self.book, None, 1, 1, self.translation)

	def test_fetch_reference_text_spans_chapters(self):
		start = ensure("Bible Verse", {"name": f"{BOOK} 1:3"}, {"book": self.book, "chapter": 1, "verse": 3})
		end = ensure("Bible Verse", {"name": f"{BOOK} 2:1"}, {"book": self.book, "chapter": 2, "verse": 1})
		reference = frappe.get_doc(
			{
				"doctype": "Bible Reference",
				"start_verse": start,
				"end_verse": end,
				"translation": self.translation,
			}
		).insert(ignore_permissions=True)

		text = fetch_reference_text(reference.name)
		self.assertEqual(text, "3. verse three 1. Chapter 2 verse one")
		self.assertEqual(frappe.db.get_value("Bible Reference", reference.name, "reference_text"), text)

	def test_fetch_reference_text_requires_a_translation(self):
		start = ensure("Bible Verse", {"name": f"{BOOK} 1:1"}, {"book": self.book, "chapter": 1, "verse": 1})
		reference = frappe.get_doc({"doctype": "Bible Reference", "start_verse": start}).insert(
			ignore_permissions=True
		)
		with self.assertRaises(ValidationError):
			fetch_reference_text(reference.name)


class TestAssignMemory(FrappeTestCase):
	def setUp(self):
		book = ensure("Bible Book", {"book": BOOK}, {"book": BOOK, "abbreviation": "TAB"})
		verse = ensure("Bible Verse", {"name": f"{BOOK} 3:1"}, {"book": book, "chapter": 3, "verse": 1})
		self.reference = ensure(
			"Bible Reference", {"start_verse": verse, "end_verse": ["is", "not set"]}, {"start_verse": verse}
		)
		self.learner = ensure_user("_test_learner@example.com", "_Test Learner")
		self.linked = make_person("_Test Assign", "Linked", user=self.learner).name
		self.unlinked = make_person("_Test Assign", "Unlinked").name
		frappe.db.delete("Bible Memory Item", {"bible_reference": self.reference})

	def tearDown(self):
		frappe.set_user("Administrator")

	def _items(self):
		return frappe.get_all(
			"Bible Memory Item", filters={"bible_reference": self.reference}, fields=["user", "assigned_by"]
		)

	def test_assigns_each_reference_to_each_user_once(self):
		result = assign_memory(frappe.as_json([self.reference]), users=self.learner)
		self.assertEqual(result, {"created": 1, "skipped": 0, "missing_users": []})
		self.assertEqual([(i.user, i.assigned_by) for i in self._items()], [(self.learner, "Administrator")])

		self.assertEqual(assign_memory([self.reference], users=[self.learner])["skipped"], 1)

	def test_group_expands_to_members_with_portal_users(self):
		group = frappe.get_doc({"doctype": "Group", "group_name": "_Test Memory Group"})
		group.append("members", {"person": self.linked})
		group.append("members", {"person": self.unlinked})
		group.insert(ignore_permissions=True)

		result = assign_memory([self.reference], group=group.name)
		self.assertEqual(result["created"], 1)
		self.assertEqual(len(result["missing_users"]), 1)
		self.assertIn(self.unlinked, result["missing_users"][0])

	def test_group_without_portal_users_is_reported(self):
		group = frappe.get_doc({"doctype": "Group", "group_name": "_Test Unlinked Group"})
		group.append("members", {"person": self.unlinked})
		group.insert(ignore_permissions=True)
		with self.assertRaises(ValidationError):
			assign_memory([self.reference], group=group.name)

	def test_requires_references_and_users(self):
		with self.assertRaises(ValidationError):
			assign_memory([], users=[self.learner])

	def test_only_managers_can_assign(self):
		frappe.set_user(self.learner)
		with self.assertRaises(PermissionError):
			assign_memory([self.reference], users=[self.learner])
