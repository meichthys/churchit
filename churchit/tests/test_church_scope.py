# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_foundations.church_access import set_user_church
from churchit.church_scope import refuse_another_churches_parent
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

MESSAGE = "{0} belongs to another church, so only that church can add notes about them."


class TestRefuseAnotherChurchesParent(RollbackEachTest):
	"""The guard a doctype that fetches `church` from a link runs on that link (Person Note here)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church_a, cls.church_b = make_two_churches()
		cls.manager_b = ensure_user("_test_parent_guard_b@example.com", "GuardB", ["Church Manager"])
		set_user_church(cls.manager_b, cls.church_b)
		cls.person_a = make_person("_Test Guard", "Person A", church=cls.church_a)
		cls.person_b = make_person("_Test Guard", "Person B", church=cls.church_b)
		cls.category = ensure("Note Category", {"category_name": "_Test Parent Guard Notes"})
		cls.addClassCleanup(frappe.clear_cache)

	def note(self, person):
		return frappe.get_doc(
			{"doctype": "Person Note", "person": person, "category": self.category, "note": "_Test"}
		)

	def saved_note(self, person):
		"""A stored note as `save` sees it, with the stored version loaded."""
		name = self.note(person).insert(ignore_permissions=True).name
		doc = frappe.get_doc("Person Note", name)
		doc.load_doc_before_save()
		return doc

	def refuse(self, doc):
		frappe.set_user(self.manager_b)
		refuse_another_churches_parent(doc, "person", MESSAGE)

	def test_a_link_to_another_churchs_record_is_refused_by_its_title(self):
		with self.assertRaisesRegex(frappe.PermissionError, self.person_a.full_name):
			self.refuse(self.note(self.person_a.name))

	def test_a_link_to_the_users_own_church_passes(self):
		self.refuse(self.note(self.person_b.name))

	def test_a_write_with_ignore_permissions_passes(self):
		note = self.note(self.person_a.name)
		note.flags.ignore_permissions = True
		self.refuse(note)

	def test_a_save_that_keeps_the_link_passes(self):
		self.refuse(self.saved_note(self.person_a.name))

	def test_moving_another_churchs_record_to_the_users_own_is_refused(self):
		"""The stored church counts too, so a record cannot be taken over by relinking it.

		The refusal names no record: the caller only guessed the stored record's name.
		"""
		note = self.saved_note(self.person_a.name)
		note.person = self.person_b.name
		with self.assertRaises(frappe.PermissionError) as refused:
			self.refuse(note)
		self.assertIn("This Person Note belongs to another church.", str(refused.exception))
		self.assertNotIn(self.person_a.full_name, str(refused.exception))

	def test_a_single_church_site_passes(self):
		force_single_church()
		self.refuse(self.note(self.person_a.name))
