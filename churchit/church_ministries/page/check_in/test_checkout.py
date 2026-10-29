# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
import frappe.client
from frappe.utils import now_datetime

from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries.page.check_in.check_in import undo_check_in
from churchit.church_ministries.page.check_in.checkout import check_out, lock_check_in
from churchit.church_ministries.page.check_in.test_check_in import check_in_with_code
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)


class TestCheckOut(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.volunteer = cls.make_volunteer("_test_checkout_volunteer_a@example.com", cls.branch_a)

	@staticmethod
	def make_volunteer(email, church):
		ensure_user(email, "Checkout", roles=("Church Check-In",))
		set_user_church(email, church)
		return email

	def setUp(self):
		super().setUp()
		function = make_function(
			"_Test Checkout Service", start_date=frappe.utils.today(), church=self.branch_a
		).name
		self.adult = check_in_with_code(function, make_person("Ada", "_Test Checkout").name, None).name
		self.child = check_in_with_code(function, make_person("Kit", "_Test Checkout").name, "CH3K").name
		frappe.set_user(self.volunteer)
		self.addCleanup(frappe.set_user, "Administrator")

	def test_a_person_without_a_pickup_tag_is_checked_out_once(self):
		check_out(self.adult)

		row = frappe.db.get_value(
			"Function Check-In", self.adult, ["collected_at", "released_by", "collected_by"], as_dict=True
		)
		self.assertTrue(row.collected_at)
		self.assertEqual((row.released_by, row.collected_by), (self.volunteer, None))
		with self.assertRaisesRegex(frappe.ValidationError, "already been checked out"):
			check_out(self.adult)

	def test_a_child_with_a_pickup_tag_leaves_only_through_verify_pickup(self):
		with self.assertRaises(frappe.PermissionError):
			check_out(self.child)
		self.assertIsNone(frappe.db.get_value("Function Check-In", self.child, "collected_at"))

	def test_a_checked_out_person_keeps_their_check_in(self):
		check_out(self.adult)

		with self.assertRaisesRegex(frappe.ValidationError, "cannot be undone"):
			undo_check_in(self.adult)
		self.assertTrue(frappe.db.exists("Function Check-In", self.adult))

		undo_check_in(self.child)
		self.assertFalse(frappe.db.exists("Function Check-In", self.child))

	def test_a_checked_out_check_in_cannot_be_deleted(self):
		check_out(self.adult)

		with self.assertRaisesRegex(frappe.ValidationError, "cannot be undone"):
			frappe.client.delete("Function Check-In", self.adult)
		self.assertTrue(frappe.db.exists("Function Check-In", self.adult))

	def test_the_checkout_fields_change_only_through_the_station(self):
		for values in (
			{"collected_at": now_datetime()},
			{"override_reason": "_Test", "overridden_by": "Administrator"},
			{"security_code": None},
		):
			with self.subTest(values), self.assertRaises(frappe.PermissionError):
				frappe.client.set_value("Function Check-In", self.child, values)

		frappe.client.set_value("Function Check-In", self.child, "notes", "_Test")
		self.assertEqual(frappe.db.get_value("Function Check-In", self.child, "security_code"), "CH3K")

	def test_a_new_check_in_brings_no_code_or_checkout(self):
		"""Frappe does not enforce read_only on insert, so a forged release or code is refused there too."""
		function, adult = frappe.db.get_value("Function Check-In", self.adult, ["function", "person"])
		new = {"doctype": "Function Check-In", "function": function, "person": make_person("Rex").name}
		for values in (
			{"security_code": "ZZZZ"},
			{"collected_at": now_datetime(), "collected_by": adult, "released_by": "Administrator"},
			{"override_reason": "_Test", "overridden_by": "Administrator"},
		):
			with self.subTest(values), self.assertRaises(frappe.PermissionError):
				frappe.client.insert({**new, **values})

		self.assertIsNone(frappe.client.insert(new)["security_code"])

	def test_a_check_in_undone_meanwhile_is_not_found(self):
		frappe.db.delete("Function Check-In", self.adult)

		with self.assertRaises(frappe.DoesNotExistError):
			lock_check_in(self.adult)

	def test_another_churchs_volunteer_checks_no_one_out(self):
		frappe.set_user(self.make_volunteer("_test_checkout_volunteer_b@example.com", self.branch_b))

		for action in (check_out, undo_check_in):
			with self.subTest(action.__name__), self.assertRaises(frappe.PermissionError):
				action(self.adult)
		self.assertIsNone(frappe.db.get_value("Function Check-In", self.adult, "collected_at"))
