# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""How often a member serves in each position: their own setting on /ministry-team and its limit."""

import frappe
from frappe.utils import add_days, getdate

from churchit.church_ministries.availability import get_problems, is_available
from churchit.church_ministries.doctype.function.function import get_time_window
from churchit.church_ministries.member_ministry_team import set_own_frequency
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
)
from churchit.www import ministry_team

ROW = "Ministry Team Position Person"


class TestServingFrequency(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.email = ensure_user("_test_frequency_member@example.com", "Frequency")
		cls.member = make_person("_Test Frequency", "Member", user=cls.email).name
		cls.stranger = make_person("_Test Frequency", "Stranger").name
		cls.greeter = make_team_position("_Test Frequency Greeter", [cls.member, cls.stranger])
		cls.usher = make_team_position("_Test Frequency Usher", [cls.stranger])

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()

	def limit_of(self, position, person):
		return frappe.db.get_value(ROW, {"parent": position.name, "person": person}, "max_times_per_month")

	def set_limit(self, person, limit):
		row = frappe.db.get_value(ROW, {"parent": self.greeter.name, "person": person})
		frappe.db.set_value(ROW, row, "max_times_per_month", limit)
		frappe.clear_document_cache("Ministry Team Position", self.greeter.name)

	def test_a_member_sees_and_sets_how_often_they_serve_in_their_positions(self):
		frappe.set_user(self.email)
		set_own_frequency(self.greeter.name, "2")

		context = frappe._dict()
		ministry_team.get_context(context)
		self.assertEqual(
			[(row.position, row.max_times_per_month) for row in context.positions], [(self.greeter.name, 2)]
		)
		frappe.set_user("Administrator")
		self.assertEqual(self.limit_of(self.greeter, self.stranger), 0)
		position = frappe.get_cached_doc("Ministry Team Position", self.greeter.name)
		self.assertEqual([row.max_times_per_month for row in position.people], [2, 0])

	def test_a_member_sets_only_their_own_row(self):
		frappe.set_user(self.email)
		with self.assertRaises(frappe.PermissionError):
			set_own_frequency(self.usher.name, 1)
		with self.assertRaises(frappe.PermissionError):
			set_own_frequency("_Test No Such Position", 1)
		with self.assertRaises(frappe.ValidationError):
			set_own_frequency(self.greeter.name, -1)

		frappe.set_user("Administrator")
		self.assertEqual(self.limit_of(self.usher, self.stranger), 0)
		self.assertEqual(self.limit_of(self.greeter, self.member), 0)

	def test_a_desk_form_opened_before_the_member_set_their_value_cannot_overwrite_it(self):
		stale = frappe.get_doc("Ministry Team Position", self.greeter.name)
		frappe.set_user(self.email)
		set_own_frequency(self.greeter.name, 3)

		frappe.set_user("Administrator")
		with self.assertRaises(frappe.TimestampMismatchError):
			stale.save()
		self.assertEqual(self.limit_of(self.greeter, self.member), 3)

	def test_a_guest_or_a_login_without_a_person_sets_nothing(self):
		ensure_user("_test_frequency_nobody@example.com", "Nobody")
		for user in ("Guest", "_test_frequency_nobody@example.com"):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				set_own_frequency(self.greeter.name, 1)

	def test_a_person_at_their_monthly_limit_is_not_available_and_the_assignment_warns(self):
		day = getdate("2031-07-06")
		served = make_function("_Test Frequency First", start_date=day)
		declined = make_function("_Test Frequency Declined", start_date=add_days(day, 1))
		next_month = make_function("_Test Frequency August", start_date="2031-08-03")
		sunday = make_function("_Test Frequency Sunday", start_date=add_days(day, 7))
		make_team_assignment(served.name, self.greeter.name, self.member, status="Accepted")
		make_team_assignment(declined.name, self.greeter.name, self.member, status="Declined")
		start, end = get_time_window(sunday)

		self.set_limit(self.member, 2)
		self.assertTrue(is_available(self.member, start, end, self.greeter.name, sunday.name))

		self.set_limit(self.member, 1)
		self.assertFalse(is_available(self.member, start, end, self.greeter.name, sunday.name))
		[problem] = get_problems(self.member, start, end, self.greeter.name, sunday.name)
		self.assertIn("at most 1 a month", problem)
		self.assertIn(problem, self.assignment(sunday).get_warnings())
		self.assertTrue(is_available(self.member, *get_time_window(next_month), self.greeter.name))

		self.set_limit(self.member, 0)
		self.assertTrue(is_available(self.member, start, end, self.greeter.name, sunday.name))

	def test_the_function_being_assigned_does_not_count_against_the_limit(self):
		sunday = make_function("_Test Frequency Own", start_date="2031-07-13")
		make_team_assignment(sunday.name, self.greeter.name, self.member)
		self.set_limit(self.member, 1)

		self.assertTrue(is_available(self.member, *get_time_window(sunday), self.greeter.name, sunday.name))

	def assignment(self, function):
		return frappe.get_doc(
			{
				"doctype": "Ministry Team Assignment",
				"function": function.name,
				"position": self.greeter.name,
				"person": self.member,
			}
		)
