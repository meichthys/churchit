# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, getdate, today

from churchit.church_people.summaries import attendance, refresh
from churchit.church_people.summaries.test_serving import queued_people
from churchit.tests.helpers import RollbackEachTest, ensure, make_function, make_person


def attend(function, person, attendance_type="Checked-In"):
	function.append("attendance", {"person": person, "attendance_type": attendance_type})
	function.save(ignore_permissions=True)


class TestAttendanceSummary(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for attendance_type in ("Checked-In", "Signed-Up", "Absent"):
			ensure("Function Attendance Type", {"type": attendance_type})

	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Attender", "Summary").name

	def summary(self):
		refresh([self.person])
		return frappe.db.get_value("Person", self.person, attendance.FIELDS, as_dict=True)

	def test_first_and_last_attended_and_the_last_90_days(self):
		attend(make_function("_Test Long Ago", start_date=add_days(today(), -200)), self.person)
		attend(make_function("_Test Lately", start_date=add_days(today(), -10)), self.person)
		attend(make_function("_Test Yesterday", start_date=add_days(today(), -1)), self.person)

		summary = self.summary()

		self.assertEqual(summary.first_attended_on, getdate(add_days(today(), -200)))
		self.assertEqual(summary.last_attended_on, getdate(add_days(today(), -1)))
		self.assertEqual(summary.times_attended_90d, 2)

	def test_only_attendance_that_means_the_person_was_there_counts(self):
		attend(make_function("_Test Signed Up", start_date=add_days(today(), -3)), self.person, "Signed-Up")
		attend(make_function("_Test Absent", start_date=add_days(today(), -2)), self.person, "Absent")

		self.assertEqual(self.summary(), {f: None for f in attendance.FIELDS} | {"times_attended_90d": 0})

	def test_a_function_still_to_come_does_not_count(self):
		attend(make_function("_Test Next Week", start_date=add_days(today(), 7)), self.person)

		self.assertIsNone(self.summary().last_attended_on)

	def test_saving_a_function_queues_everyone_it_had_or_has(self):
		function = make_function("_Test Roster", start_date=today())
		attend(function, self.person)
		other = make_person("_Test Newcomer", "Summary").name
		function.attendance = []
		function.append("attendance", {"person": other, "attendance_type": "Checked-In"})

		queued = queued_people(lambda: function.save(ignore_permissions=True))

		self.assertEqual(queued, [sorted([self.person, other])])
