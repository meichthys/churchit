# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	get_function_item_totals,
	get_function_items,
	get_item_status,
)
from churchit.tests.helpers import make_function


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


class TestFunctionSignUpItems(FrappeTestCase):
	"""Sign-up item totals across the sign-ups for one function."""

	def setUp(self):
		self.item = _ensure("Sign-Up Item", {"item": "_Test Dish"}, {"item": "_Test Dish"})
		self.other_item = _ensure("Sign-Up Item", {"item": "_Test Drink"}, {"item": "_Test Drink"})
		self.function = make_function("_Test Potluck", allow_sign_ups=1)
		self.function.append("table_cxhh", {"item": self.item, "quantity_needed": 5})
		self.function.append("table_cxhh", {"item": self.other_item, "quantity_needed": 2})
		self.function.save(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in frappe.get_all(
			"Function Sign-Up", filters={"function": self.function.name}, pluck="name"
		):
			frappe.delete_doc("Function Sign-Up", name, force=True, ignore_permissions=True)

	def _sign_up(self, first_name, quantity):
		person = _ensure("Person", {"first_name": first_name}, {"first_name": first_name})
		sign_up = frappe.get_doc(
			{"doctype": "Function Sign-Up", "function": self.function.name, "person": person}
		)
		sign_up.append("table_iprj", {"item": self.item, "my_quantity": quantity})
		return sign_up.insert(ignore_permissions=True)

	def test_item_row_mirrors_the_quantity_needed_from_the_function(self):
		sign_up = self._sign_up("_Test Bringer One", 2)
		self.assertEqual(sign_up.table_iprj[0].quantity_needed, 5)

	def test_item_status_sums_quantities_across_sign_ups(self):
		first = self._sign_up("_Test Bringer One", 2)
		self._sign_up("_Test Bringer Two", 3)

		self.assertEqual(
			get_item_status(self.function.name, self.item),
			{"quantity_needed": 5, "quantity_signed_up": 5},
		)
		# Excluding one sign-up shows what everyone else brings.
		self.assertEqual(
			get_item_status(self.function.name, self.item, exclude_sign_up=first.name)["quantity_signed_up"],
			3,
		)

	def test_item_totals_cover_every_configured_item(self):
		self._sign_up("_Test Bringer One", 4)
		self.assertEqual(
			get_function_item_totals(self.function.name),
			{
				self.item: {"quantity_needed": 5, "quantity_signed_up": 4},
				self.other_item: {"quantity_needed": 2, "quantity_signed_up": 0},
			},
		)

	def test_function_items_search_is_scoped_to_the_function(self):
		rows = get_function_items("Sign-Up Item", "Dish", "name", 0, 20, {"function": self.function.name})
		self.assertEqual([row[0] for row in rows], [self.item])
		self.assertEqual(get_function_items("Sign-Up Item", "", "name", 0, 20, {}), [])
