# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.api.v1 import update_doc
from frappe.desk.reportview import get as report_builder_rows
from frappe.utils import getdate

from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.doctype.note_category.note_category import GENERAL
from churchit.church_people.notes import get_alert_notes, get_timeline_notes, search_categories_to_add
from churchit.church_people.privacy import anonymize
from churchit.patches.v1_0.add_note_categories_and_move_person_notes import execute as move_person_notes
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

OPEN = "_Test Open Notes"
PASTORAL = "_Test Pastoral Notes"
PRIVATE = "_Test Private Notes"
# Everyone with a right on Person Note reads it; only the care team adds to it.
CARE_WRITES = "_Test Care Writes"


def make_category(name, view_roles=(), create_roles=(), ignore_permissions=True, **values):
	frappe.get_doc(
		{
			"doctype": "Note Category",
			"category_name": name,
			"view_roles": [{"role": role} for role in view_roles],
			"create_roles": [{"role": role} for role in create_roles],
			**values,
		}
	).insert(ignore_permissions=ignore_permissions)


def make_note(person, category, note, author="Administrator", **values):
	"""The name of a new note by *author*, written without checking their rights."""
	frappe.set_user(author)
	try:
		doc = {"doctype": "Person Note", "person": person, "category": category, "note": note, **values}
		return frappe.get_doc(doc).insert(ignore_permissions=True).name
	finally:
		frappe.set_user("Administrator")


def update_by_rest(user, name, **values):
	"""PUT /api/resource/Person Note/<name> as *user*."""
	frappe.set_user(user)
	frappe.local.form_dict = frappe._dict(data=json.dumps(values))
	try:
		return update_doc("Person Note", name)
	finally:
		frappe.set_user("Administrator")


def listed_notes(user, person):
	frappe.set_user(user)
	try:
		return set(frappe.get_list("Person Note", filters={"person": person}, pluck="name"))
	finally:
		frappe.set_user("Administrator")


class NoteTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.staff = ensure_user("_test_notes_staff@example.com", "Staff", ["Church Staff"])
		cls.carer = ensure_user(
			"_test_notes_carer@example.com", "Carer", ["Church Staff", "Church Pastoral Care"]
		)
		cls.editor = ensure_user(
			"_test_notes_editor@example.com", "Editor", ["Church Staff", "Church People Editor"]
		)
		cls.manager = ensure_user("_test_notes_manager@example.com", "Manager", ["Church Manager"])
		make_category(OPEN)
		make_category(PASTORAL, ["Church Pastoral Care"], ["Church Pastoral Care"])
		make_category(PRIVATE, is_private=1)
		make_category(CARE_WRITES, create_roles=["Church Pastoral Care"])
		cls.person = make_person("_Test Noted", "Person").name


class TestNoteCategoryAccess(NoteTestCase):
	def setUp(self):
		super().setUp()
		self.open_note = make_note(self.person, OPEN, "_Test open text")
		self.pastoral_note = make_note(self.person, PASTORAL, "_Test pastoral text")

	def test_lists_leave_out_categories_the_reader_may_not_read(self):
		self.assertEqual(listed_notes(self.staff, self.person), {self.open_note})
		self.assertEqual(listed_notes(self.carer, self.person), {self.open_note, self.pastoral_note})

	def test_a_note_opens_only_for_its_categorys_readers(self):
		self.assertTrue(frappe.has_permission("Person Note", "read", self.pastoral_note, user=self.carer))
		self.assertFalse(frappe.has_permission("Person Note", "read", self.pastoral_note, user=self.staff))
		self.assertFalse(frappe.has_permission("Person Note", "print", self.pastoral_note, user=self.staff))
		self.assertTrue(frappe.has_permission("Person Note", "read", self.open_note, user=self.staff))

	def test_report_builder_leaves_out_categories_the_reader_may_not_read(self):
		frappe.set_user(self.staff)
		frappe.local.form_dict = frappe._dict(
			doctype="Person Note",
			fields=json.dumps(["`tabPerson Note`.`name`"]),
			filters=json.dumps([["Person Note", "person", "=", self.person]]),
		)

		rows = report_builder_rows()["values"]

		self.assertEqual([row[0] for row in rows], [self.open_note])

	def test_the_timeline_shows_only_the_notes_the_reader_may_read(self):
		frappe.set_user(self.staff)
		staff_cards = "".join(card["content"] for card in get_timeline_notes("Person", self.person))
		frappe.set_user(self.carer)
		carer_cards = "".join(card["content"] for card in get_timeline_notes("Person", self.person))

		self.assertIn("_Test open text", staff_cards)
		self.assertNotIn("_Test pastoral text", staff_cards)
		self.assertIn("_Test pastoral text", carer_cards)

	def test_the_timeline_is_empty_for_a_role_without_notes(self):
		frappe.set_user(ensure_user("_test_notes_check_in@example.com", "Check In", ["Church Check-In"]))
		self.assertEqual(get_timeline_notes("Person", self.person), [])

	def test_a_private_category_is_read_only_by_the_author(self):
		mine = make_note(self.person, PRIVATE, "_Test carer's own", author=self.carer)
		theirs = make_note(self.person, PRIVATE, "_Test staff's own", author=self.staff)
		system_manager = ensure_user("_test_notes_system@example.com", "System", ["System Manager"])

		self.assertEqual(listed_notes(self.carer, self.person) & {mine, theirs}, {mine})
		self.assertEqual(listed_notes(self.manager, self.person) & {mine, theirs}, set())
		self.assertEqual(listed_notes(system_manager, self.person) & {mine, theirs}, set())
		self.assertTrue(frappe.has_permission("Person Note", "read", mine, user=self.carer))
		self.assertFalse(frappe.has_permission("Person Note", "read", mine, user=self.manager))

	def test_adding_a_note_in_a_category_needs_its_adding_role(self):
		frappe.set_user(self.staff)
		refused = frappe.get_doc(
			{"doctype": "Person Note", "person": self.person, "category": CARE_WRITES, "note": "_Test"}
		)
		self.assertRaises(frappe.PermissionError, refused.insert)

		allowed = frappe.get_doc(
			{"doctype": "Person Note", "person": self.person, "category": OPEN, "note": "_Test"}
		)
		allowed.insert()
		self.assertEqual(allowed.owner, self.staff)

	def test_changing_a_note_needs_its_adding_role(self):
		note = make_note(self.person, CARE_WRITES, "_Test read by all")

		self.assertTrue(frappe.has_permission("Person Note", "read", note, user=self.editor))
		self.assertFalse(frappe.has_permission("Person Note", "write", note, user=self.editor))
		self.assertTrue(frappe.has_permission("Person Note", "write", note, user=self.carer))

	def test_the_category_picker_offers_only_categories_the_user_may_add_to(self):
		frappe.set_user(self.staff)
		offered = [row[0] for row in search_categories_to_add("Note Category", "_Test", "name", 0, 20, {})]

		self.assertIn(OPEN, offered)
		self.assertNotIn(PASTORAL, offered)
		self.assertNotIn(CARE_WRITES, offered)

	def test_the_alert_lookup_returns_readable_alerts_pinned_first(self):
		alert = make_note(self.person, OPEN, "_Test alert", is_alert=1, noted_on="2026-01-02")
		pinned = make_note(
			self.person, OPEN, "_Test pinned alert", is_alert=1, is_pinned=1, noted_on="2026-01-01"
		)
		make_note(self.person, PASTORAL, "_Test pastoral alert", is_alert=1)

		frappe.set_user(self.staff)

		self.assertEqual([row.name for row in get_alert_notes(self.person)], [pinned, alert])


class TestNoteChanges(NoteTestCase):
	def test_a_note_cannot_be_refiled_into_a_category_the_user_may_read(self):
		note = make_note(self.person, PASTORAL, "_Test pastoral text")

		with self.assertRaises(frappe.PermissionError):
			update_by_rest(self.editor, note, category=OPEN)

		self.assertEqual(frappe.db.get_value("Person Note", note, "category"), PASTORAL)

	def test_a_private_note_cannot_be_refiled_or_taken_over_by_another_user(self):
		note = make_note(self.person, PRIVATE, "_Test carer's own", author=self.carer)

		for user, values in ((self.editor, {"category": OPEN}), (self.staff, {"owner": self.staff})):
			with self.subTest(values), self.assertRaises(frappe.PermissionError):
				update_by_rest(user, note, **values)

		self.assertEqual(
			frappe.db.get_value("Person Note", note, ["category", "owner"]), (PRIVATE, self.carer)
		)

	def test_a_user_who_may_change_a_note_may_refile_it(self):
		note = make_note(self.person, PASTORAL, "_Test pastoral text")

		update_by_rest(self.carer, note, category=OPEN)

		self.assertEqual(frappe.db.get_value("Person Note", note, "category"), OPEN)


class TestNoteCategoryChurches(NoteTestCase):
	def setUp(self):
		super().setUp()
		self.root, self.branch_a, _branch_b = make_two_churches()
		set_user_church(self.manager, self.branch_a)

	def as_user(self, change, user=None):
		frappe.set_user(user or self.manager)
		try:
			change()
		finally:
			frappe.set_user("Administrator")

	def changed(self, name, **values):
		def save():
			category = frappe.get_doc("Note Category", name)
			category.update(values)
			category.save()

		return save

	def test_a_branch_manager_cannot_change_who_reads_or_adds_notes(self):
		make_category("_Test Branch Delete")
		refused = {
			"untick private": self.changed(PRIVATE, is_private=0),
			"widen readers": self.changed(PASTORAL, view_roles=[]),
			"widen adders": self.changed(PASTORAL, create_roles=[{"role": "Church Staff"}]),
			"add": lambda: make_category("_Test Branch New", ignore_permissions=False),
			"delete": lambda: frappe.delete_doc("Note Category", "_Test Branch Delete"),
		}
		for change, attempt in refused.items():
			with self.subTest(change), self.assertRaises(frappe.PermissionError):
				self.as_user(attempt)

		self.assertEqual(frappe.db.get_value("Note Category", PRIVATE, "is_private"), 1)
		self.assertTrue(frappe.db.exists("Note Category", "_Test Branch Delete"))

	def test_a_branch_manager_may_still_describe_a_category(self):
		self.as_user(self.changed(OPEN, description="_Test described"))
		self.assertEqual(frappe.db.get_value("Note Category", OPEN, "description"), "_Test described")

	def test_a_manager_of_the_main_church_changes_who_reads_notes(self):
		main = ensure_user("_test_notes_main_manager@example.com", "Main Manager", ["Church Manager"])
		set_user_church(main, self.root)

		self.as_user(self.changed(PRIVATE, is_private=0), main)
		self.as_user(lambda: make_category("_Test Main New", ignore_permissions=False), main)

		self.assertEqual(frappe.db.get_value("Note Category", PRIVATE, "is_private"), 0)
		self.assertTrue(frappe.db.exists("Note Category", "_Test Main New"))

	def test_on_a_single_church_site_every_manager_changes_categories(self):
		force_single_church()
		self.as_user(self.changed(PRIVATE, is_private=0))
		self.assertEqual(frappe.db.get_value("Note Category", PRIVATE, "is_private"), 0)


class TestNoteScope(NoteTestCase):
	def test_a_note_belongs_to_its_persons_church(self):
		_root, branch_a, branch_b = make_two_churches()
		note_a = make_note(make_person("_Test Noted A", church=branch_a).name, OPEN, "_Test A")
		note_b = make_note(make_person("_Test Noted B", church=branch_b).name, OPEN, "_Test B")
		set_user_church(self.manager, branch_a)

		self.assertEqual(frappe.db.get_value("Person Note", note_a, "church"), branch_a)
		assert_scoped(self, "Person Note", self.manager, note_a, note_b)

	def test_a_note_about_another_churches_person_is_refused(self):
		_root, branch_a, branch_b = make_two_churches()
		person_a = make_person("_Test Noted A", church=branch_a).name
		person_b = make_person("_Test Noted B", church=branch_b).name
		set_user_church(self.manager, branch_a)
		frappe.set_user(self.manager)

		note = {"doctype": "Person Note", "category": OPEN, "note": "_Test", "is_alert": 1}
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({**note, "person": person_b}).insert()
		mine = frappe.get_doc({**note, "person": person_a}).insert().name

		with self.assertRaises(frappe.PermissionError):
			update_by_rest(self.manager, mine, person=person_b)
		self.assertEqual(frappe.db.get_value("Person Note", mine, "person"), person_a)

	def test_anonymizing_a_person_deletes_their_notes(self):
		note = make_note(self.person, PASTORAL, "_Test about to go")

		anonymize(self.person)

		self.assertFalse(frappe.db.exists("Person Note", note))
		self.assertFalse(frappe.db.exists("Deleted Document", {"deleted_name": note}))


class TestMovePersonNotes(RollbackEachTest):
	def test_each_persons_notes_move_once_into_general(self):
		if not frappe.db.has_column("Person", "notes"):
			self.skipTest("This site never had the Person Notes field.")
		noted = make_person("_Test Moved", "Notes")
		blank = make_person("_Test Blank", "Notes")
		Person = frappe.qb.DocType("Person")
		for person, value in ((noted.name, "<p>Prefers the early service</p>"), (blank.name, "<p><br></p>")):
			frappe.qb.update(Person).set(Person.notes, value).where(Person.name == person).run()

		move_person_notes()
		move_person_notes()

		notes = frappe.get_all(
			"Person Note",
			filters={"person": ("in", [noted.name, blank.name])},
			fields=["person", "category", "noted_on", "note"],
		)
		self.assertEqual(
			[(row.person, row.category, row.noted_on, row.note) for row in notes],
			[(noted.name, GENERAL, getdate(noted.creation), "<p>Prefers the early service</p>")],
		)
		left = frappe.qb.from_(Person).select(Person.notes).where(Person.name.isin([noted.name, blank.name]))
		self.assertEqual(left.run(), ((None,), (None,)))
