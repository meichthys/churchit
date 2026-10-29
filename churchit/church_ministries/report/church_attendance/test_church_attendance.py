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
