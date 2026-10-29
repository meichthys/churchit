# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.api.v1 import document_list, read_doc

from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries.page.check_in.test_pickup_release import make_restriction
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure_user,
	make_person,
	make_two_churches,
)


class TestPickupRestriction(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def setUp(self):
		super().setUp()
		self.child = make_person("Kim", "_Test Restricted", church=self.branch_a).name
		self.stranger = make_person("Rex", "_Test Restricted", church=self.branch_a).name
		self.restriction = make_restriction(self.child, self.stranger, reason="_Test Court order").name
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())

	def user(self, email, role, church):
		ensure_user(email, "Restriction", roles=(role,))
		set_user_church(email, church)
		return email

	def test_a_check_in_volunteer_cannot_open_a_restriction(self):
		frappe.set_user(
			self.user("_test_restriction_check_in_a@example.com", "Church Check-In", self.branch_a)
		)
		try:
			with self.assertRaises(frappe.PermissionError):
				read_doc("Pickup Restriction", self.restriction)
			frappe.local.form_dict = frappe._dict(fields='["reason"]')
			with self.assertRaises(frappe.PermissionError):
				document_list("Pickup Restriction")
		finally:
			frappe.set_user("Administrator")

	def test_a_people_editor_sees_only_their_churchs_restrictions(self):
		child_b = make_person("Kai", "_Test Restricted", church=self.branch_b).name
		theirs = make_restriction(child_b, None, restricted_name="_Test Someone").name
		editor_a = self.user("_test_restriction_editor_a@example.com", "Church People Editor", self.branch_a)
		editor_b = self.user("_test_restriction_editor_b@example.com", "Church People Editor", self.branch_b)

		assert_scoped(self, "Pickup Restriction", editor_b, theirs, self.restriction)
		frappe.set_user(editor_b)
		try:
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc(
					{
						"doctype": "Pickup Restriction",
						"child": self.child,
						"restricted_name": "_Test Someone",
						"description": "_Test",
					}
				).insert()
		finally:
			frappe.set_user("Administrator")
		assert_scoped(self, "Pickup Restriction", editor_a, self.restriction, theirs)

	def test_a_court_order_is_a_private_file(self):
		for is_private in (0, 1):
			doc = frappe.get_doc("Pickup Restriction", self.restriction)
			file = frappe.get_doc(
				{"doctype": "File", "file_name": "_test_order.txt", "content": "x", "is_private": is_private}
			).insert(ignore_permissions=True)
			self.addCleanup(frappe.delete_doc, "File", file.name, force=True, ignore_permissions=True)
			doc.court_order = file.file_url
			if is_private:
				doc.save(ignore_permissions=True)
			else:
				with self.assertRaisesRegex(frappe.ValidationError, "private file"):
					doc.save(ignore_permissions=True)

	def test_a_restriction_names_someone_other_than_the_child(self):
		for values in ({}, {"restricted_person": self.child}):
			with self.subTest(values), self.assertRaises(frappe.ValidationError):
				frappe.get_doc(
					{"doctype": "Pickup Restriction", "child": self.child, "description": "_Test", **values}
				).insert(ignore_permissions=True)
