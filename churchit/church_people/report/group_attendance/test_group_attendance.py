# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, today

from churchit.church_ministries.attendance import record
from churchit.church_people.report.group_attendance.group_attendance import execute
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)


def days_ago(days):
	return add_days(today(), -days)


def make_group(group_name, church, people=(), **values):
	group = frappe.get_doc({"doctype": "Group", "group_name": group_name, "church": church, **values})
	for person in people:
		group.append("members", {"person": person})
	return group.insert(ignore_permissions=True).name


def make_meeting(function_name, group, start_date, attendance=(), **values):
	function = make_function(function_name, group=group, start_date=start_date, **values)
	for person, status in attendance:
		record(person, function.name, status)
	return function.name


class TestGroupAttendance(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.group_type = ensure("Group Type", {"type": "_Test Attendance Type"})
		people = [
			make_person("_Test Group Attender", str(number), church=cls.branch_a).name
			for number in (1, 2, 3, 4)
		]
		cls.group = make_group("_Test Attendance Group", cls.branch_a, people, group_type=cls.group_type)
		first, second, third, fourth = people
		make_meeting(
			"_Test Group Meeting One",
			cls.group,
			days_ago(14),
			[(first, "Checked-In"), (second, "Confirmed"), (third, "Signed-Up")],
			church=cls.branch_a,
		)
		make_meeting(
			"_Test Group Meeting Two",
			cls.group,
			days_ago(7),
			[(first, "Assumed"), (second, "Absent")],
			church=cls.branch_a,
		)
		make_meeting(
			"_Test Group Not Met",
			cls.group,
			days_ago(3),
			[(first, "Checked-In")],
			church=cls.branch_a,
			did_not_meet=1,
		)
		make_meeting(
			"_Test Group Ahead", cls.group, add_days(today(), 7), [(fourth, "Confirmed")], church=cls.branch_a
		)

		cls.other_group = make_group("_Test Attendance Other Group", cls.branch_b)
		make_meeting("_Test Other Group Meeting", cls.other_group, days_ago(7), church=cls.branch_b)

	def rows(self, **filters):
		_columns, data = execute({"from_date": days_ago(84), "to_date": today(), **filters})
		return {
			row.group: (row.meetings_held, row.average_attendance, row.members, row.attendance_rate)
			for row in data
			if row.group in (self.group, self.other_group)
		}

	def test_counts_only_held_past_meetings_and_counted_attendance(self):
		self.assertEqual(self.rows()[self.group], (2, 1.5, 4, 37.5))

	def test_a_group_schedule_is_not_a_meeting(self):
		make_meeting(
			"_Test Group Schedule",
			self.group,
			days_ago(21),
			church=self.branch_a,
			auto_repeat=1,
			repeat_frequency="Weekly",
		)

		self.assertEqual(self.rows()[self.group][0], 2)

	def test_the_date_range_and_the_group_filters_narrow_the_rows(self):
		self.assertEqual(self.rows(from_date=days_ago(10))[self.group], (1, 1.0, 4, 25.0))
		self.assertEqual(set(self.rows(group=self.other_group)), {self.other_group})
		self.assertEqual(set(self.rows(group_type=self.group_type)), {self.group})

	def test_a_church_manager_sees_only_the_groups_of_their_church(self):
		manager = ensure_user("_test_group_attendance_b@example.com", "ManagerB", roles=("Church Manager",))
		make_person("ManagerB", "Group Attendance", church=self.branch_b, user=manager)
		frappe.set_user(manager)

		self.assertEqual(set(self.rows()), {self.other_group})
		self.assertRaises(frappe.PermissionError, self.rows, group=self.group)
