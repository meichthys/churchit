# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The serving reads of AI apps answer as the caller: their churches and the reports their roles open."""

from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate

from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries.ai import get_open_needs
from churchit.church_people import ai as people_ai
from churchit.church_people.test_ai import AITestCase, as_user, set_ai
from churchit.tests.helpers import ensure, ensure_user, make_function, make_team_position


class TestOpenNeeds(AITestCase):
	def setUp(self):
		super().setUp()
		self.needs = {church: self.make_need(church) for church in (self.branch_a, self.branch_b)}

	def make_need(self, church):
		"""A function of *church* in three days that needs one person in a position nobody fills."""
		ministry = {"ministry_name": f"_Test AI Ministry {church}", "church": church}
		ministry = ensure("Ministry", {"ministry_name": ministry["ministry_name"]}, ministry)
		position = make_team_position(f"_Test AI Greeter {church}", [], ministry_name=ministry, church=church)
		return make_function(
			f"_Test AI Sunday {church}",
			church=church,
			start_date=add_days(getdate(), 3),
			team_needs=[{"position": position.name, "quantity": 1}],
		).name

	def test_the_caller_sees_the_open_places_of_their_churches(self):
		page = as_user(self.manager, get_open_needs)

		functions = {row["function"] for row in page["rows"]}
		self.assertIn(self.needs[self.branch_a], functions)
		self.assertNotIn(self.needs[self.branch_b], functions)
		row = next(row for row in page["rows"] if row["function"] == self.needs[self.branch_a])
		self.assertEqual((row["needed"], row["open"]), (1, 1))
		self.assertIn("query-report/Ministry%20Team%20Schedule", page["url"])

	def test_a_role_the_report_does_not_open_to_is_refused(self):
		check_in = ensure_user("_test_ai_needs_check_in@example.com", "AI Check-In", ["Church Check-In"])
		set_user_church(check_in, self.branch_a)

		self.assertRaises(frappe.PermissionError, as_user, check_in, get_open_needs)

	def test_dates_outside_the_window_are_left_out_and_a_long_window_is_refused(self):
		later = add_days(getdate(), 4)
		rows = as_user(self.manager, get_open_needs, str(later), str(add_days(later, 7)))["rows"]
		self.assertNotIn(self.needs[self.branch_a], {row["function"] for row in rows})
		self.assertRaises(
			frappe.ValidationError,
			as_user,
			self.manager,
			get_open_needs,
			str(getdate()),
			str(add_days(getdate(), 93)),
		)

	def test_one_page_and_the_total(self):
		self.make_need(self.branch_a)

		with patch.object(people_ai, "PAGE", 1):
			page = as_user(self.manager, get_open_needs)

		self.assertEqual(len(page["rows"]), 1)
		self.assertGreaterEqual(page["total"], 2)

	def test_a_portal_member_and_ai_off_are_refused(self):
		self.assertRaises(frappe.PermissionError, as_user, self.member, get_open_needs)
		set_ai(0)
		self.assertRaises(frappe.PermissionError, as_user, self.manager, get_open_needs)
