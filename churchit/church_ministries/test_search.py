# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.client import validate_link_and_fetch
from frappe.desk.search import search_link
from frappe.utils import add_days, getdate

from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries.search import search_functions
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_function, make_two_churches

NAME = "_Test Function Search"


def found(txt=NAME, **arguments):
	return [row["value"] for row in search_link("Function", txt, **arguments)]


def on(days_from_today, **values):
	"""A function *days_from_today* days from today."""
	return make_function(NAME, start_date=add_days(getdate(), days_from_today), **values).name


class TestFunctionSearch(RollbackEachTest):
	def test_coming_functions_come_first_soonest_first_then_past_ones_latest_first(self):
		far = on(60)
		last_week = on(-7)
		today = on(0)
		next_week = on(7)
		last_year = on(-365)

		self.assertEqual(found(), [today, next_week, far, last_week, last_year])

	def test_this_week_is_offered_before_functions_made_far_ahead(self):
		weeks_ahead = [on(7 * week) for week in range(2, 14)]
		this_week = on(3)

		self.assertEqual(found(page_length=10), [this_week, *weeks_ahead[:9]])

	def test_pages_continue_from_coming_into_past_functions(self):
		coming = [on(days) for days in (1, 2, 3)]
		past = [on(days) for days in (-1, -2, -3)]

		rows = search_functions("Function", NAME, "name", start=2, page_len=3, filters={})

		self.assertEqual([row[0] for row in rows], [coming[2], past[0], past[1]])

	def test_a_row_shows_the_title_type_and_time_without_seconds(self):
		name = on(1, start_time="10:00:00")
		row = next(row for row in search_link("Function", NAME) if row["value"] == name)

		self.assertTrue(row["label"].startswith(NAME))
		self.assertIn("_Test Function Type", row["description"])
		self.assertIn("10:00 AM", row["description"])
		self.assertNotIn("10:00:00", row["description"])

	def test_the_fields_filters_apply_and_a_picked_function_validates(self):
		open_for_sign_up = on(1, allow_sign_ups=1)
		on(2)

		self.assertEqual(found(filters={"allow_sign_ups": 1}), [open_for_sign_up])
		frappe.local.request = frappe._dict(method="POST")
		self.addCleanup(delattr, frappe.local, "request")
		self.assertEqual(validate_link_and_fetch("Function", open_for_sign_up)["name"], open_for_sign_up)

	def test_a_user_finds_only_the_functions_of_their_church(self):
		_root, branch_a, branch_b = make_two_churches()
		mine = on(1, church=branch_a)
		theirs = on(1, church=branch_b)
		staff = ensure_user(
			"_test_function_search_staff@example.com", "FunctionSearch", roles=("Church Staff",)
		)
		set_user_church(staff, branch_a)

		frappe.set_user(staff)
		self.assertIn(mine, found())
		self.assertNotIn(theirs, found())
