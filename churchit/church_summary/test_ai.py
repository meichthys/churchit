# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The week overview of AI apps answers as the caller: their churches, their to-dos, their fields."""

from unittest.mock import patch

import frappe
from frappe.utils import getdate

from churchit.church_foundations.church_access import set_user_church
from churchit.church_people import ai as people_ai
from churchit.church_people.doctype.follow_up_card.test_follow_up_card import make_workflow
from churchit.church_people.followup import add_card
from churchit.church_people.test_ai import LAST_NAME, AITestCase, as_user, raise_permission_level, set_ai
from churchit.church_summary.ai import get_week_overview
from churchit.tests.helpers import ensure_user, make_function, make_person

# A Wednesday; its week runs from Monday 5 May to Sunday 11 May 2031.
WEDNESDAY = "2031-05-07"


def names(page):
	return [row["name"] for row in page["rows"]]


class TestWeekOverview(AITestCase):
	def test_the_week_runs_monday_to_sunday_with_the_functions_of_the_callers_churches(self):
		mine = make_function("_Test AI Week Mine", church=self.branch_a, start_date="2031-05-11").name
		theirs = make_function("_Test AI Week Theirs", church=self.branch_b, start_date="2031-05-08").name
		later = make_function("_Test AI Week Later", church=self.branch_a, start_date="2031-05-12").name

		overview = as_user(self.manager, get_week_overview, WEDNESDAY)

		self.assertEqual(overview["week"], [getdate("2031-05-05"), getdate("2031-05-11")])
		self.assertIn(mine, names(overview["functions"]))
		self.assertNotIn(theirs, names(overview["functions"]))
		self.assertNotIn(later, names(overview["functions"]))

	def test_follow_ups_are_the_callers_own_open_to_dos(self):
		workflow = make_workflow(
			"_Test AI Week Calls", [("Call", self.manager, 2)], church=self.branch_a
		).name
		card = add_card(make_person("Called", LAST_NAME, church=self.branch_a).name, workflow)

		mine = as_user(self.manager, get_week_overview, WEDNESDAY)["follow_ups"]["rows"]
		others = as_user(self.staff, get_week_overview, WEDNESDAY)["follow_ups"]["rows"]

		self.assertEqual([(row["reference_name"], row["description"][:4]) for row in mine], [(card, "Call")])
		self.assertEqual(others, [])

	def test_a_part_the_caller_may_not_read_is_left_out(self):
		check_in = ensure_user("_test_ai_week_check_in@example.com", "AI Week Check-In", ["Church Check-In"])
		set_user_church(check_in, self.branch_a)

		overview = as_user(check_in, get_week_overview, WEDNESDAY)

		self.assertNotIn("guests", overview)
		self.assertIn("guests", as_user(self.manager, get_week_overview, WEDNESDAY))

	def test_a_field_the_caller_may_not_read_is_left_out(self):
		function = make_function("_Test AI Week Titled", church=self.branch_a, start_date=WEDNESDAY).name
		raise_permission_level(self, "Function", "title")

		rows = as_user(self.staff, get_week_overview, WEDNESDAY)["functions"]["rows"]

		self.assertNotIn("title", next(row for row in rows if row["name"] == function))

	def test_one_page_and_the_total(self):
		for name in ("_Test AI Week One", "_Test AI Week Two"):
			make_function(name, church=self.branch_a, start_date=WEDNESDAY)

		with patch.object(people_ai, "PAGE", 1):
			functions = as_user(self.manager, get_week_overview, WEDNESDAY)["functions"]

		self.assertEqual(len(functions["rows"]), 1)
		self.assertGreaterEqual(functions["total"], 2)

	def test_a_portal_member_and_ai_off_are_refused(self):
		self.assertRaises(frappe.PermissionError, as_user, self.member, get_week_overview)
		set_ai(0)
		self.assertRaises(frappe.PermissionError, as_user, self.manager, get_week_overview)
