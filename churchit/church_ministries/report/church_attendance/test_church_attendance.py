# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, today

from churchit.church_ministries.attendance import record
from churchit.church_ministries.report.church_attendance.church_attendance import execute
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)


class GroupMeetings:
	"""Shared by the attendance report tests: a Church A group meeting, a Church B group meeting and a
	Church A service with no group. A test class sets `function_field` and `rows`."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, branch_a, branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.group = cls.make_group("_Test Trend Group", branch_a)
		cls.other_group = cls.make_group("_Test Trend Other Group", branch_b)
		cls.meeting = cls.make_attended("_Test Trend Meeting", branch_a, cls.group)
		cls.other_meeting = cls.make_attended("_Test Trend Other Meeting", branch_b, cls.other_group)
		cls.service = cls.make_attended("_Test Trend Service", branch_a)
		cls.manager_b = ensure_user(
			"_test_trend_manager_b@example.com", "ManagerB", roles=("Church Manager",)
		)
		make_person("ManagerB", "Trend", church=branch_b, user=cls.manager_b)

	@staticmethod
	def make_group(group_name, church):
		return (
			frappe.get_doc({"doctype": "Group", "group_name": group_name, "church": church})
			.insert(ignore_permissions=True)
			.name
		)

	@staticmethod
	def make_attended(function_name, church, group=None):
		function = make_function(function_name, start_date=add_days(today(), -7), church=church, group=group)
		record(make_person(function_name, church=church).name, function.name, "Checked-In")
		return function.name

	def groups_by_function(self, **filters):
		"""{function: group} of this class's functions in the report, from its function field."""
		ours = (self.meeting, self.other_meeting, self.service)
		return {
			row[self.function_field]: row.group
			for row in self.rows(**filters)
			if row[self.function_field] in ours
		}

	def test_a_group_filter_keeps_only_that_groups_meetings(self):
		self.assertEqual(self.groups_by_function(group=self.group), {self.meeting: self.group})

	def test_with_no_group_filter_every_function_stays_with_its_group(self):
		self.assertEqual(
			self.groups_by_function(),
			{self.meeting: self.group, self.other_meeting: self.other_group, self.service: None},
		)

	def test_a_manager_who_names_another_churchs_group_is_refused(self):
		frappe.set_user(self.manager_b)

		self.assertRaises(frappe.PermissionError, self.rows, group=self.group)
		self.assertEqual(self.groups_by_function(), {self.other_meeting: self.other_group})


class TestChurchAttendance(GroupMeetings, RollbackEachTest):
	function_field = "name"

	def rows(self, **filters):
		return execute(filters)[1]

	def test_a_manager_who_names_another_churchs_function_is_refused(self):
		frappe.set_user(self.manager_b)

		self.assertRaises(frappe.PermissionError, self.rows, function=self.meeting)


class TestChurchAttendanceFilters(RollbackEachTest):
	def attended(self, name, days_ago, person):
		function = make_function(name, start_date=add_days(today(), -days_ago))
		record(person, function.name, "Checked-In")
		return function.name

	def test_the_report_has_a_date_and_lists_the_latest_function_first(self):
		person = make_person("_Test Attendance Order").name
		older = self.attended("_Test Attendance Older", 20, person)
		newer = self.attended("_Test Attendance Newer", 3, person)
		# A later edit of the older function does not move it up.
		frappe.db.set_value("Function", older, "headcount", 5)

		columns, rows = execute({"function": older})
		self.assertEqual(columns[0]["fieldname"], "start_date")
		self.assertEqual([row.name for row in rows], [older])

		names = [row.name for row in execute({})[1] if row.name in (older, newer)]
		self.assertEqual(names, [newer, older])

	def test_the_date_filters_keep_the_functions_in_the_range(self):
		person = make_person("_Test Attendance Range").name
		old = self.attended("_Test Attendance Old", 40, person)
		recent = self.attended("_Test Attendance Recent", 3, person)

		rows = execute({"from_date": add_days(today(), -28), "to_date": today()})[1]
		names = {row.name for row in rows}
		self.assertIn(recent, names)
		self.assertNotIn(old, names)
