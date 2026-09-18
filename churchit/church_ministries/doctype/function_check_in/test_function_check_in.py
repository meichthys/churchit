# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_ministries.doctype.function_check_in.function_check_in import (
	check_in_persons,
	print_name_tags,
)
from churchit.tests.helpers import make_function, make_person


class TestFunctionCheckIn(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.get_single("Check-In Settings").save(ignore_permissions=True)

	def setUp(self):
		self.function = make_function("_Test Check-In Function")
		self.person = make_person("_Test Check-In", "Person")

	def _check_in(self, person=None):
		return frappe.get_doc(
			{
				"doctype": "Function Check-In",
				"function": self.function.name,
				"person": person or self.person.name,
			}
		).insert(ignore_permissions=True)

	def _attendance_for(self, person):
		function = frappe.get_doc("Function", self.function.name)
		return [row.attendance_type for row in function.attendance if row.person == person]

	def test_title_is_built_from_function_and_person(self):
		self.assertEqual(self._check_in().title, "_Test Check-In Function - _Test Check-In Person")

	def test_duplicate_check_in_is_rejected(self):
		self._check_in()
		with self.assertRaises(ValidationError):
			self._check_in()

	def test_check_in_adds_a_checked_in_attendance_row(self):
		self._check_in()
		self.assertEqual(self._attendance_for(self.person.name), ["Checked-In"])

	def test_check_in_upgrades_an_existing_attendance_row(self):
		self.function.append("attendance", {"person": self.person.name, "attendance_type": "Signed-Up"})
		self.function.save(ignore_permissions=True)

		self._check_in()
		self.assertEqual(self._attendance_for(self.person.name), ["Checked-In"])

	def test_deleting_check_in_removes_the_attendance_row(self):
		self._check_in().delete()
		self.assertEqual(self._attendance_for(self.person.name), [])

	def test_check_in_persons_accepts_a_json_list_and_is_idempotent(self):
		other = make_person("_Test Check-In", "Other").name
		people = json.dumps([self.person.name, other])

		check_in_persons(self.function.name, people)
		check_in_persons(self.function.name, people)

		check_ins = frappe.get_all(
			"Function Check-In", filters={"function": self.function.name}, pluck="person"
		)
		self.assertEqual(sorted(check_ins), sorted([self.person.name, other]))
		self.assertEqual(self._attendance_for(other), ["Checked-In"])

	def test_new_check_ins_in_one_call_share_a_security_code(self):
		frappe.db.set_single_value("Check-In Settings", "security_codes", 1)
		other = make_person("_Test Check-In", "Sibling").name
		names = check_in_persons(self.function.name, [self.person.name, other])
		codes = {frappe.db.get_value("Function Check-In", name, "security_code") for name in names}
		self.assertEqual(len(codes), 1)
		self.assertRegex(codes.pop(), r"^[A-Z2-9]{4}$")
		frappe.db.set_single_value("Check-In Settings", "security_codes", 0)

	def test_check_ins_have_no_security_code_unless_enabled(self):
		self.assertIsNone(self._check_in().security_code)

	def test_print_name_tags_needs_something_to_print(self):
		with self.assertRaises(ValidationError):
			print_name_tags()
