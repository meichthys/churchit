# Copyright (c) 2025, meichthys and Contributors
# See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


def _ensure_church_user(email, first_name):
	if not frappe.db.exists("User", email):
		user = frappe.new_doc("User")
		user.update({"email": email, "first_name": first_name})
		user.flags.no_welcome_mail = True
		user.append("roles", {"role": "Church User"})
		user.insert(ignore_permissions=True)
	return email


class TestFunctionSignUp(FrappeTestCase):
	def setUp(self):
		self.function_type = _ensure(
			"Function Type", {"type": "_Test Signup Type"}, {"type": "_Test Signup Type"}
		)
		self.function = _ensure(
			"Function",
			{"function_name": "_Test Signup Function"},
			{
				"function_name": "_Test Signup Function",
				"type": self.function_type,
				"start_date": "2031-05-01",
				"allow_sign_ups": 1,
			},
		)
		self.closed_function = _ensure(
			"Function",
			{"function_name": "_Test Closed Function"},
			{
				"function_name": "_Test Closed Function",
				"type": self.function_type,
				"start_date": "2031-05-01",
				"allow_sign_ups": 0,
			},
		)
		self.person = _ensure("Person", {"first_name": "_Test Signer"}, {"first_name": "_Test Signer"})
		self.other_person = _ensure("Person", {"first_name": "_Test Other"}, {"first_name": "_Test Other"})

	def tearDown(self):
		# Sign-ups outlive the per-test rollback, and the duplicate guard would then
		# trip on rows left behind by earlier tests in the same run.
		frappe.set_user("Administrator")
		for name in frappe.get_all(
			"Function Sign-Up",
			filters={"function": ["in", [self.function, self.closed_function]]},
			pluck="name",
		):
			frappe.delete_doc("Function Sign-Up", name, force=True, ignore_permissions=True)

	def _sign_up(self, person=None, function=None, **values):
		return frappe.get_doc(
			{
				"doctype": "Function Sign-Up",
				"function": function or self.function,
				"person": person or self.person,
				**values,
			}
		).insert(ignore_permissions=True)

	def _attendance_for(self, person):
		function_doc = frappe.get_doc("Function", self.function)
		return [row.attendance_type for row in function_doc.attendance if row.person == person]

	def test_sign_up_blocked_when_function_disallows_it(self):
		with self.assertRaises(ValidationError):
			self._sign_up(function=self.closed_function)

	def test_duplicate_sign_up_for_same_person_is_rejected(self):
		self._sign_up()
		with self.assertRaises(ValidationError):
			self._sign_up()

	def test_manager_can_sign_up_on_behalf_of_another_person(self):
		self.assertEqual(self._sign_up(person=self.other_person).person, self.other_person)

	def test_non_manager_cannot_sign_up_as_someone_else(self):
		email = _ensure_church_user("_test_signup_user@example.com", "_Test Signup User")
		frappe.db.set_value("Person", self.person, "user", email)
		frappe.set_user(email)
		# Submitting someone else's Person must be overridden with the caller's own.
		self.assertEqual(self._sign_up(person=self.other_person).person, self.person)

	def test_non_manager_without_a_person_record_is_rejected(self):
		frappe.set_user(_ensure_church_user("_test_orphan_user@example.com", "_Test Orphan"))
		with self.assertRaises(ValidationError):
			self._sign_up()

	def test_attending_adds_a_signed_up_attendance_row(self):
		self._sign_up(attending=1)
		self.assertEqual(self._attendance_for(self.person), ["Signed-Up"])

	def test_not_attending_adds_no_attendance_row(self):
		self._sign_up(attending=0)
		self.assertEqual(self._attendance_for(self.person), [])

	def test_clearing_attending_removes_the_attendance_row(self):
		sign_up = self._sign_up(attending=1)
		sign_up.attending = 0
		sign_up.save(ignore_permissions=True)
		self.assertEqual(self._attendance_for(self.person), [])

	def test_deleting_sign_up_removes_the_attendance_row(self):
		self._sign_up(attending=1).delete()
		self.assertEqual(self._attendance_for(self.person), [])

	def test_title_is_built_from_function_and_person(self):
		self.assertIn("_Test Signup Function", self._sign_up().title)
