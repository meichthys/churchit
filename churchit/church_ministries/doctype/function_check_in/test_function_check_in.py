# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from itertools import chain
from unittest.mock import Mock, patch

import frappe
from frappe.api.v1 import update_doc
from frappe.exceptions import ValidationError
from frappe.handler import is_valid_http_method
from frappe.tests.utils import FrappeTestCase

from churchit.church_ministries.doctype.function_check_in.function_check_in import (
	VOLUNTEER,
	add_check_ins,
	check_in_persons,
	new_security_code,
	print_name_tags,
)
from churchit.church_ministries.page.check_in.check_in import add_visitor
from churchit.church_ministries.page.check_in.check_in import check_in as station_check_in
from churchit.church_people.test_household import make_household
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)

CHECK_IN = "Function Check-In"
MODULE = "churchit.church_ministries.doctype.function_check_in.function_check_in"


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

	def use_security_codes(self):
		frappe.db.set_single_value("Check-In Settings", "security_codes", 1)
		self.addCleanup(frappe.db.set_single_value, "Check-In Settings", "security_codes", 0)

	def get_code(self, check_ins):
		(code,) = {frappe.db.get_value(CHECK_IN, name, "security_code") for name in check_ins}
		return code

	def test_a_household_checked_in_by_two_calls_on_one_day_keeps_one_code(self):
		self.use_security_codes()
		family, _father, _mother, son, _grandmother = make_household("_Test Code Household", "Codeton")
		daughter = make_person("Dot", "Codeton", family=family).name
		second_service = make_function("_Test Check-In Second Service").name

		code = self.get_code(check_in_persons(self.function.name, [son]))
		self.assertEqual(self.get_code(check_in_persons(second_service, [daughter])), code)

	def test_a_second_household_never_gets_a_code_held_today(self):
		self.use_security_codes()
		held = self.get_code(check_in_persons(self.function.name, [self.person.name]))
		stranger = make_person("_Test Check-In", "Stranger").name

		draws = chain([held], iter(new_security_code, None))
		with patch(f"{MODULE}.new_security_code", side_effect=draws) as draw:
			code = self.get_code(check_in_persons(self.function.name, [stranger]))
		self.assertNotEqual(code, held)
		self.assertGreater(draw.call_count, 1)

	def test_a_check_in_locks_the_function_then_the_code_then_the_check_ins(self):
		"""The check-ins found are read with a lock: a plain read answers from the request's older snapshot,
		so a second station that waited on the Function lock would miss the first one's check-in."""
		(existing,) = add_check_ins(self.function.name, [self.person.name])
		locks = Mock()
		for method in ("get_value", "get_single_value", "get_values"):
			locks.attach_mock(
				self.enterContext(patch.object(frappe.db, method, wraps=getattr(frappe.db, method))), method
			)

		self.assertEqual(add_check_ins(self.function.name, [self.person.name]), [existing])

		locked = [call.args[0] for call in locks.mock_calls if call.kwargs.get("for_update")]
		self.assertEqual(list(dict.fromkeys(locked)), ["Function", "Check-In Settings", CHECK_IN])

	def test_a_person_named_twice_in_one_call_gets_one_check_in(self):
		names = add_check_ins(self.function.name, [self.person.name, self.person.name])
		self.assertEqual(len(set(names)), 1)
		self.assertEqual(len(names), 2)

	def test_a_call_with_no_kind_stores_a_regular_check_in(self):
		(name,) = check_in_persons(self.function.name, [self.person.name])
		self.assertEqual(frappe.db.get_value(CHECK_IN, name, "check_in_kind"), "Regular")

	def test_a_volunteer_check_in_gets_no_security_code(self):
		self.use_security_codes()
		(name,) = add_check_ins(self.function.name, [self.person.name], VOLUNTEER)
		self.assertIsNone(frappe.db.get_value(CHECK_IN, name, "security_code"))
		self.assertEqual(self._attendance_for(self.person.name), ["Checked-In"])

	def test_a_visitor_added_at_the_station_is_checked_in_as_a_guest(self):
		visitor = add_visitor("_Test Check-In", "Visitor")["name"]
		(name,) = station_check_in(self.function.name, [visitor], kind="Guest")["check_ins"]
		self.assertEqual(frappe.db.get_value(CHECK_IN, name, "check_in_kind"), "Guest")
		self.assertEqual(self._attendance_for(visitor), ["Checked-In"])

	def test_check_ins_have_no_security_code_unless_enabled(self):
		self.assertIsNone(self._check_in().security_code)

	def test_print_name_tags_needs_something_to_print(self):
		with self.assertRaises(ValidationError):
			print_name_tags()

	def test_print_name_tags_refuses_get(self):
		"""With a network printer it prints at once, so another site's GET must not start it.

		test_http_method_hygiene.py cannot see this: a socket send is not a write it knows.
		"""
		frappe.local.request = frappe._dict(method="GET")
		self.addCleanup(delattr, frappe.local, "request")
		with self.assertRaises(frappe.PermissionError):
			is_valid_http_method(print_name_tags)


class TestFunctionCheckInChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.volunteer_a = ensure_user("_test_check_in_a@example.com", "Volunteer", roles=("Church Check-In",))
		make_person("_Test Check-In", "Volunteer", church=cls.branch_a, user=cls.volunteer_a)
		cls.function_a = make_function("_Test Check-In A", church=cls.branch_a).name
		cls.function_b = make_function("_Test Check-In B", church=cls.branch_b).name
		cls.first, cls.second = (make_person("_Test Check-In", name).name for name in ("First", "Second"))

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def test_only_the_functions_church_checks_people_in_or_moves_a_check_in(self):
		"""Frappe checks the church the caller sends, before the check-in takes the function's church."""
		theirs = frappe.new_doc(CHECK_IN, function=self.function_b, person=self.second).insert().name
		frappe.set_user(self.volunteer_a)

		with self.assertRaises(frappe.PermissionError):
			frappe.new_doc(CHECK_IN, function=self.function_b, person=self.first).insert()
		self.assertEqual(
			frappe.new_doc(CHECK_IN, function=self.function_a, person=self.first).insert().church,
			self.branch_a,
		)

		frappe.local.form_dict = frappe._dict(
			data=json.dumps({"function": self.function_a, "church": self.branch_a})
		)
		with self.assertRaises(frappe.PermissionError):
			update_doc(CHECK_IN, theirs)
		self.assertEqual(frappe.db.get_value(CHECK_IN, theirs, "function"), self.function_b)
