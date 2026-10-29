# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.doctype.note_category.note_category import (
	BENEVOLENCE,
	PASTORAL_CARE,
	PASTORAL_ROLES,
)
from churchit.patches.v1_0 import add_benevolence_note_category
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person


def drop_category(name):
	"""Remove *name* as a site that never had it, without the checks a delete runs."""
	frappe.db.delete("Note Category Role", {"parent": name})
	frappe.db.delete("Note Category", name)
	frappe.clear_document_cache("Note Category", name)


class TestBenevolenceCategory(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		add_benevolence_note_category.execute()
		cls.staff = ensure_user("_test_benevolence_staff@example.com", "Staff", ["Church Staff"])
		cls.carer = ensure_user(
			"_test_benevolence_carer@example.com", "Carer", ["Church Staff", "Church Pastoral Care"]
		)
		cls.finance = ensure_user("_test_benevolence_finance@example.com", "Finance", ["Church Finance"])
		cls.person = make_person("_Test Benevolence", "Recipient").name

	def test_the_patch_adds_benevolence_once_with_the_care_roles(self):
		drop_category(BENEVOLENCE)

		add_benevolence_note_category.execute()
		add_benevolence_note_category.execute()

		self.assertEqual(frappe.db.count("Note Category", {"name": BENEVOLENCE}), 1)
		category = frappe.get_doc("Note Category", BENEVOLENCE)
		self.assertEqual({row.role for row in category.view_roles}, set(PASTORAL_ROLES))
		self.assertEqual({row.role for row in category.create_roles}, set(PASTORAL_ROLES))
		self.assertFalse(category.is_private)

	def test_the_patch_brings_back_no_other_category(self):
		drop_category(PASTORAL_CARE)

		add_benevolence_note_category.execute()

		self.assertFalse(frappe.db.exists("Note Category", PASTORAL_CARE))

	def test_only_the_care_team_reads_a_benevolence_note(self):
		note = frappe.get_doc(
			{
				"doctype": "Person Note",
				"person": self.person,
				"category": BENEVOLENCE,
				"note": "_Test rent help",
			}
		).insert(ignore_permissions=True)

		for user, can_read in ((self.carer, True), (self.staff, False), (self.finance, False)):
			with self.subTest(user=user):
				self.assertEqual(frappe.has_permission("Person Note", "read", note, user=user), can_read)

		for user, can_read in ((self.carer, True), (self.staff, False)):
			frappe.set_user(user)
			listed = frappe.get_list("Person Note", filters={"person": self.person}, pluck="name")
			self.assertEqual(note.name in listed, can_read, user)
