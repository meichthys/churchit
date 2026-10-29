# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.tests.utils import FrappeTestCase

from churchit.church_people import celebrations
from churchit.tests.helpers import ensure, make_person

START, END = "2031-12-28", "2032-01-03"


def born_on(date):
	return [{"event_type": "Birth", "date": date}]


class TestCelebrations(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Member Status", {"status": "Active"})
		cls.inactive = ensure("Member Status", {"status": "Inactive"})
		cls.member = ensure("Membership Type", {"type": "Member"})
		cls.visitor = ensure("Membership Type", {"type": "Visitor"})

	def test_birthdays_in_a_window_across_the_new_year(self):
		make_person("Late", "_Test December", membership=self.member, life_events=born_on("1990-12-30"))
		make_person("Early", "_Test January", membership=self.member, life_events=born_on("1985-01-02"))
		make_person("Leap", "_Test Day", membership=self.member, life_events=born_on("1988-02-29"))
		make_person("Outside", "_Test Window", membership=self.member, life_events=born_on("1990-01-04"))
		make_person("Visiting", "_Test Guest", membership=self.visitor, life_events=born_on("1990-12-31"))
		make_person(
			"Moved",
			"_Test Away",
			membership=self.member,
			membership_status=self.inactive,
			life_events=born_on("1990-12-31"),
		)

		rows = [(row.day, row.name) for row in celebrations.birthdays(START, END)]

		self.assertEqual(rows[:2], [("Dec 30", "Late _Test December"), ("Jan 2", "Early _Test January")])
		self.assertNotIn(("Jan 4", "Outside _Test Window"), rows)
		self.assertNotIn(("Dec 31", "Visiting _Test Guest"), rows)
		self.assertNotIn(("Dec 31", "Moved _Test Away"), rows)
		self.assertIn(
			("Feb 28", "Leap _Test Day"),
			[(r.day, r.name) for r in celebrations.birthdays("2031-02-28", "2031-02-28")],
		)

	def test_hidden_people_and_their_anniversaries_are_left_out(self):
		make_person(
			"Shy",
			"_Test Hidden",
			membership=self.member,
			hide_from_directory=1,
			life_events=born_on("1990-12-30"),
		)
		partner = make_person("Partner", "_Test Hidden", membership=self.member, hide_from_directory=1)
		make_person(
			"Open",
			"_Test Hidden",
			membership=self.member,
			marital_status="Married",
			anniversary="2010-12-29",
			spouse=partner.name,
		)

		names = [row.name for row in celebrations.birthdays(START, END)]
		names += [row.name for row in celebrations.anniversaries(START, END)]
		self.assertFalse([name for name in names if "_Test Hidden" in name])

	def test_people_who_have_died_and_their_anniversaries_are_left_out(self):
		ensure("Life Event Type", {"type": "Death"})
		widow = make_person("Widow", "_Test Late", membership=self.visitor, life_events=born_on("1950-12-30"))
		make_person(
			"Husband",
			"_Test Late",
			membership=self.visitor,
			marital_status="Married",
			anniversary="1975-12-29",
			spouse=widow.name,
			life_events=[*born_on("1950-12-31"), {"event_type": "Death", "date": "2024-01-01"}],
		)

		names = [row.name for row in celebrations.birthdays(START, END, members_only=False)]
		names += [row.name for row in celebrations.anniversaries(START, END, members_only=False)]

		self.assertIn("Widow _Test Late", names)
		self.assertFalse([name for name in names if "Husband" in name])

	def test_everyone_includes_non_members(self):
		make_person("Visiting", "_Test Everyone", membership=self.visitor, life_events=born_on("1990-12-31"))
		rows = celebrations.birthdays(START, END, members_only=False)
		self.assertIn("Visiting _Test Everyone", [row.name for row in rows])

	def test_a_birthday_with_no_year_is_listed(self):
		make_person(
			"Yearless",
			"_Test Birthday",
			membership=self.member,
			life_events=[{"event_type": "Birth", "date": "1900-07-04", "year_unknown": 1}],
		)

		rows = [(row.day, row.name) for row in celebrations.birthdays("2031-07-01", "2031-07-07")]

		self.assertIn(("Jul 4", "Yearless _Test Birthday"), rows)

	def test_anniversaries_list_each_couple_once(self):
		# Person links spouses both ways on save.
		sarah = make_person("Sarah", "_Test Smith", membership=self.member)
		make_person(
			"Matt",
			"_Test Smith",
			membership=self.member,
			marital_status="Married",
			anniversary="2010-12-29",
			spouse=sarah.name,
		)
		ann = make_person("Ann", "_Test Jones", membership=self.member)
		make_person(
			"Ben",
			"_Test Brown",
			membership=self.member,
			marital_status="Married",
			anniversary="2005-01-01",
			spouse=ann.name,
		)
		make_person("Single", "_Test Widow", membership=self.member, anniversary="2005-01-01")

		rows = [(row.day, row.name) for row in celebrations.anniversaries(START, END)]

		smiths = [name for day, name in rows if "_Test Smith" in name]
		self.assertEqual(len(smiths), 1)
		self.assertIn(smiths[0], ("Matt & Sarah _Test Smith", "Sarah & Matt _Test Smith"))
		mixed = [name for day, name in rows if "_Test Jones" in name or "_Test Brown" in name]
		self.assertEqual(len(mixed), 1)
		self.assertIn(mixed[0], ("Ben _Test Brown & Ann _Test Jones", "Ann _Test Jones & Ben _Test Brown"))
		self.assertNotIn("Single _Test Widow", [name for day, name in rows])
