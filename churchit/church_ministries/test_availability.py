# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import itertools

import frappe
from frappe.utils import add_days, getdate

from churchit.church_ministries.availability import get_blocks_covering, get_problems, is_available, rank
from churchit.church_ministries.doctype.function.function import get_time_window
from churchit.church_ministries.member_ministry_team import add_own_block, get_own_blocks
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
)


def block(person, from_date, to_date=None, **values):
	return frappe.get_doc(
		{
			"doctype": "Ministry Team Block",
			"person": person,
			"from_date": from_date,
			"to_date": to_date or from_date,
			**values,
		}
	).insert(ignore_permissions=True)


class TestAvailability(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.person = make_person("_Test Availability", "Person").name
		cls.position = make_team_position("_Test Availability Usher", [cls.person])
		cls.sunday = make_function(
			"_Test Availability Sunday", start_date="2031-06-01", start_time="10:00:00", end_time="11:00:00"
		)

	def covered(self, on_date):
		return [b.name for b in get_blocks_covering(self.person, on_date, on_date)]

	def test_get_problems_gives_the_assignment_warnings_without_the_email_one(self):
		check_type = ensure("Background Check Type", {"type": "_Test Availability Check"})
		nursery = make_team_position(
			"_Test Availability Nursery",
			[self.person],
			needs_background_check=1,
			required_checks=[{"check_type": check_type}],
		)
		block(self.person, "2031-06-01", reason="Away")
		overlapping = make_function(
			"_Test Availability Overlap", start_date="2031-06-01", start_time="10:30:00", end_time="12:00:00"
		)
		make_team_assignment(overlapping.name, self.position.name, self.person)
		assignment = frappe.get_doc(
			{
				"doctype": "Ministry Team Assignment",
				"function": self.sunday.name,
				"position": nursery.name,
				"person": self.person,
			}
		)

		start, end = get_time_window(self.sunday)
		problems = get_problems(self.person, start, end, nursery.name, self.sunday.name)
		self.assertEqual(len(problems), 3, problems)
		[email_warning] = [w for w in assignment.get_warnings() if w not in problems]
		self.assertIn("no email address", email_warning)
		self.assertEqual(assignment.get_warnings(), [*problems, email_warning])

	def test_a_deceased_person_or_one_with_a_problem_is_not_available(self):
		start, end = get_time_window(self.sunday)
		self.assertTrue(is_available(self.person, start, end, self.position.name))

		frappe.db.set_value("Person", self.person, "is_deceased", 1)
		self.assertFalse(is_available(self.person, start, end, self.position.name))

		frappe.db.set_value("Person", self.person, "is_deceased", 0)
		block(self.person, "2031-06-01")
		self.assertFalse(is_available(self.person, start, end, self.position.name))

	def test_rank_asks_who_served_longest_ago_then_least_then_by_name(self):
		figures = {
			"Recent": ("2031-05-20", 1),
			"Busy": ("2031-05-01", 4),
			"Quiet": ("2031-05-01", 1),
			"Never A": (None, 0),
			"Never B": (None, 0),
		}
		people = {}
		for first_name, (last_served_on, times) in figures.items():
			people[first_name] = make_person(first_name, "_Test Rank").name
			frappe.db.set_value(
				"Person",
				people[first_name],
				{"last_served_on": last_served_on, "times_served_90d": times},
				update_modified=False,
			)

		never = sorted([people["Never A"], people["Never B"]])
		expected = [*never, people["Quiet"], people["Busy"], people["Recent"]]
		for order in itertools.permutations(people.values()):
			self.assertEqual(rank(list(order)), expected)

	def test_a_monthly_block_repeats_the_weekday_and_week_of_the_month(self):
		first_sunday = block(self.person, "2026-11-01", repeat_frequency="Monthly on the Same Weekday").name
		self.assertEqual(self.covered("2026-12-06"), [first_sunday])
		self.assertEqual(self.covered("2026-12-13"), [])

	def test_a_block_on_a_fifth_weekday_covers_only_months_that_have_one(self):
		fifth_sunday = block(self.person, "2026-11-29", repeat_frequency="Monthly on the Same Weekday").name
		self.assertEqual(get_blocks_covering(self.person, "2026-12-01", "2026-12-31"), [])
		self.assertEqual(self.covered("2027-01-31"), [fifth_sunday])

	def test_an_every_other_week_block_skips_the_week_between(self):
		fortnightly = block(self.person, "2026-11-01", repeat_frequency="Every Other Week").name
		self.assertEqual(self.covered("2026-11-15"), [fortnightly])
		self.assertEqual(self.covered("2026-11-08"), [])

	def test_a_weekly_block_covers_nothing_after_repeat_until(self):
		weekly = block(
			self.person, "2026-11-01", "2026-11-03", repeat_frequency="Weekly", repeat_until="2026-11-15"
		).name
		self.assertEqual(self.covered("2026-11-15"), [weekly])
		self.assertEqual(get_blocks_covering(self.person, "2026-11-16", "2027-12-31"), [])

	def test_a_repeating_block_with_no_end_keeps_covering(self):
		weekly = block(self.person, "2026-01-04", repeat_frequency="Weekly").name
		self.assertEqual(self.covered("2031-06-01"), [weekly])
		self.assertEqual(self.covered("2031-06-02"), [])

	def test_the_warning_names_the_repeat_that_covers_the_function(self):
		block(self.person, "2031-05-04", repeat_frequency="Weekly", reason="Choir")
		start, end = get_time_window(self.sunday)
		[problem] = get_problems(self.person, start, end)
		self.assertIn(frappe.utils.format_date("2031-06-01"), problem)
		self.assertIn("Choir", problem)

	def test_a_repeat_must_end_before_it_starts_again(self):
		with self.assertRaisesRegex(frappe.ValidationError, "at most 7 days"):
			block(self.person, "2026-11-01", "2026-11-08", repeat_frequency="Weekly")
		with self.assertRaisesRegex(frappe.ValidationError, "Repeat Until"):
			block(
				self.person, "2026-11-01", "2026-11-03", repeat_frequency="Weekly", repeat_until="2026-11-02"
			)
		self.assertIsNone(block(self.person, "2026-11-01", repeat_until="2026-12-01").repeat_until)


class TestOwnRepeatingBlocks(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.email = ensure_user("_test_availability_member@example.com", "Availability")
		cls.member = make_person("_Test Availability", "Member", user=cls.email).name

	def test_a_block_without_a_repeat_is_one_time(self):
		frappe.set_user(self.email)
		tomorrow = str(add_days(getdate(), 1))
		add_own_block(tomorrow, tomorrow, "Away")

		[own] = get_own_blocks(self.member)
		self.assertEqual(own.reason, "Away")
		self.assertFalse(own.repeat_frequency or own.repeat_until)

	def test_a_member_adds_a_repeating_block(self):
		frappe.set_user(self.email)
		tomorrow = str(add_days(getdate(), 1))
		until = str(add_days(getdate(), 60))
		add_own_block(tomorrow, tomorrow, "Choir", 0, "Every Other Week", until)

		[own] = get_own_blocks(self.member)
		self.assertEqual((own.repeat_frequency, str(own.repeat_until)), ("Every Other Week", until))

	def test_a_repeat_not_on_the_list_is_refused(self):
		frappe.set_user(self.email)
		tomorrow = str(add_days(getdate(), 1))
		with self.assertRaises(frappe.ValidationError):
			add_own_block(tomorrow, tomorrow, "Choir", 0, "Daily")
		self.assertEqual(get_own_blocks(self.member), [])

	def test_repeating_blocks_stay_listed_while_they_still_repeat(self):
		past = add_days(getdate(), -30)
		running = block(self.member, past, repeat_frequency="Weekly").name
		ending = block(self.member, past, repeat_frequency="Weekly", repeat_until=add_days(getdate(), 5)).name
		block(self.member, past, repeat_frequency="Weekly", repeat_until=add_days(getdate(), -1))
		block(self.member, past)

		self.assertEqual(sorted(b.name for b in get_own_blocks(self.member)), sorted([running, ending]))
