# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_ministries.page.check_in.check_in import check_in
from churchit.church_ministries.page.check_in.visitors import find_visitor_matches
from churchit.tests.helpers import (
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
	set_private_people,
)

PHONE = "555 010 4477"


def phones(number):
	return [{"phone_number": number, "is_primary": 1}]


class TestVisitorMatches(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.volunteer = ensure_user(
			"_test_visitor_match_a@example.com", "VisitorMatchA", roles=("Church Check-In",)
		)
		make_person("VisitorMatchA", "Volunteer", church=cls.branch_a, user=cls.volunteer)
		cls.service = make_function("_Test Visitor Match Service", church=cls.branch_a).name
		cls.joint = make_function("_Test Visitor Match Joint", church=cls.branch_b, is_shared=1).name
		cls.ours = make_person("Vince", "_Test Visitormatch", church=cls.branch_a, phones=phones(PHONE)).name
		cls.theirs = make_person(
			"Vera", "_Test Visitormatch", church=cls.branch_b, phones=phones("555 010 4488")
		).name
		cls.addClassCleanup(frappe.clear_cache)

	def tearDown(self):
		frappe.set_user("Administrator")

	def matches(self, function, first_name, phone):
		groups = find_visitor_matches(function, first_name, "_Test Visitormatch", phone)
		return [member.name for group in groups for member in group["members"] if member.matched]

	def test_a_visitor_already_on_file_is_offered_with_their_family(self):
		frappe.set_user(self.volunteer)
		self.assertEqual(self.matches(self.service, "Vince", PHONE), [self.ours])
		self.assertEqual(self.matches(self.service, "Victor", "555 010 9999"), [])

	def test_a_visitor_who_gives_only_their_name_is_offered_the_same_named_person(self):
		frappe.set_user(self.volunteer)
		self.assertEqual(self.matches(self.service, " Vince ", None), [self.ours])
		self.assertEqual(self.matches(self.service, "Vin", None), [])

	def test_a_private_directory_hides_another_churchs_match_except_at_a_shared_function(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)

		frappe.set_user(self.volunteer)
		self.assertEqual(self.matches(self.service, "Vera", "555 010 4488"), [])
		self.assertEqual(self.matches(self.joint, "Vera", "555 010 4488"), [self.theirs])

	def test_choosing_a_match_checks_them_in_and_creates_no_person(self):
		frappe.set_user(self.volunteer)
		(match,) = self.matches(self.service, "Vince", PHONE)
		people = frappe.db.count("Person")

		check_in(self.service, [match])

		self.assertEqual(frappe.db.count("Person"), people)
		self.assertTrue(frappe.db.exists("Function Check-In", {"function": self.service, "person": match}))

	def test_only_a_check_in_user_who_may_read_the_function_is_answered(self):
		staff = ensure_user(
			"_test_visitor_match_staff@example.com", "VisitorMatchStaff", roles=("Church Staff",)
		)
		their_service = make_function("_Test Visitor Match Their Service", church=self.branch_b).name

		frappe.set_user(staff)
		with self.assertRaises(frappe.PermissionError):
			find_visitor_matches(self.service, "Vince", "_Test Visitormatch", PHONE)

		frappe.set_user(self.volunteer)
		with self.assertRaises(frappe.PermissionError):
			find_visitor_matches(their_service, "Vince", "_Test Visitormatch", PHONE)
