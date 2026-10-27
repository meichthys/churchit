# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.utils import add_days, today

from churchit.church_ministries.attendance import record
from churchit.church_people.report.attendance_count.attendance_count import execute
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_function,
	make_person,
	make_two_churches,
)


def days_ago(*days):
	return [add_days(today(), -day) for day in days]


def attend(person, dates, status="Checked-In", **values):
	"""Give *person* a row of type *status* on a new Function on each of *dates*."""
	for date in dates:
		function = make_function(f"_Test Count {person} {date}", start_date=date, **values)
		record(person, function.name, status)
	return person


def make_attendance_list(name, **filters):
	"""A Custom Report of Attendance Count with its saved *filters*, as the report's menu > Save makes it."""
	return frappe.get_doc(
		{
			"doctype": "Report",
			"report_name": name,
			"ref_doctype": "Person",
			"report_type": "Custom Report",
			"reference_report": "Attendance Count",
			"is_standard": "No",
			"json": json.dumps({"filters": filters, "columns": []}),
		}
	).insert(ignore_permissions=True)


def counts(people, **filters):
	"""{person: times attended} of *people* in the report run with *filters*; the site may hold others."""
	rows = execute({"from_date": add_days(today(), -60), **filters})[1]
	return {row.person: row.times_attended for row in rows if row.person in people}


class TestAttendanceCount(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def setUp(self):
		super().setUp()
		self.people = []

	def person(self, first_name):
		self.people.append(make_person(first_name, "_Test Attendance Count").name)
		return self.people[-1]

	def test_the_people_who_attended_at_least_min_times_since_the_date(self):
		often = attend(self.person("Often"), days_ago(5, 12, 19))
		twice = attend(self.person("Twice"), days_ago(5, 12, 90))

		self.assertEqual(counts(self.people, min_times=3), {often: 3})
		self.assertEqual(counts(self.people, min_times=2), {often: 3, twice: 2})

	def test_a_future_function_and_an_uncounted_type_do_not_count(self):
		ahead = attend(self.person("Ahead"), [*days_ago(5, 12), add_days(today(), 3)])
		absent = attend(self.person("Absent"), days_ago(5, 12))
		attend(absent, days_ago(19), status="Absent")

		self.assertEqual(counts(self.people, min_times=2), {ahead: 2, absent: 2})
		self.assertEqual(counts(self.people, min_times=3), {})

	def test_until_and_the_function_type_narrow_the_count(self):
		service = ensure("Function Type", {"type": "_Test Count Service"})
		person = attend(self.person("Narrow"), days_ago(5, 12, 19))
		attend(person, days_ago(26), type=service)

		self.assertEqual(counts(self.people, to_date=add_days(today(), -10)), {person: 3})
		self.assertEqual(counts(self.people, function_type=service), {person: 1})

	def test_the_dead_are_left_out(self):
		died = attend(self.person("Died"), days_ago(5))
		frappe.db.set_value("Person", died, "is_deceased", 1)

		self.assertEqual(counts(self.people), {})

	def test_no_since_date_gives_no_rows(self):
		attend(self.person("Undated"), days_ago(5))

		self.assertEqual(execute({})[1], [])


class TestAttendanceCountChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.manager_b = ensure_user("_test_count_manager_b@example.com", "CountB", roles=("Church Manager",))
		make_person("CountB", "Manager", church=cls.branch_b, user=cls.manager_b)

	def test_a_reader_sees_only_their_churches_people_and_their_own_churches_functions(self):
		mine = make_person("_Test Count Mine", church=self.branch_b).name
		attend(mine, days_ago(5, 12), church=self.branch_b)
		attend(mine, days_ago(19), church=self.branch_a)
		theirs = make_person("_Test Count Theirs", church=self.branch_a).name
		attend(theirs, days_ago(5), church=self.branch_a)

		frappe.set_user(self.manager_b)
		self.addCleanup(frappe.set_user, "Administrator")
		self.assertEqual(counts([mine, theirs]), {mine: 2})
