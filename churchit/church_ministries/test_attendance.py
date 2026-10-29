# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from churchit.church_ministries.attendance import (
	record,
	refresh_started_totals,
	remove,
	set_headcount,
)
from churchit.church_ministries.doctype.function.function import Function
from churchit.church_ministries.doctype.function_check_in.function_check_in import check_in_persons
from churchit.church_ministries.report.church_attendance import church_attendance
from churchit.church_ministries.report.function_attendance_by_person import function_attendance_by_person
from churchit.church_ministries.report.function_attendance_by_type import function_attendance_by_type
from churchit.church_people.report.inactive_members import inactive_members
from churchit.church_people.report.visitor_log import visitor_log
from churchit.church_people.summaries.test_serving import queued_people
from churchit.dashboard import count_weekly_attendance
from churchit.patches.v1_0 import zero_future_attendance_totals
from churchit.tests.helpers import (
	ensure_root_church,
	ensure_user,
	make_branch,
	make_function,
	make_person,
	set_multi_church,
)


def make_attended_function(function_name, start_date, people, attendance_type):
	function = make_function(function_name, start_date=start_date)
	for person in people:
		function.append("attendance", {"person": person, "attendance_type": attendance_type})
	return function.save(ignore_permissions=True)


class TestAttendance(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.people = [
			make_person(f"_Test Roster {number}", membership="Member", membership_status="Active").name
			for number in (1, 2, 3)
		]

	def test_a_future_roster_counts_nowhere(self):
		before = count_weekly_attendance()["value"]
		function = make_attended_function("_Test Roster Ahead", add_days(today(), 1), self.people, "Assumed")

		self.assertEqual(function.attendance_total, 0)
		self.assertEqual(count_weekly_attendance()["value"], before)
		self.assertNotIn(function.name, {row.name for row in church_attendance.get_data({})})
		self.assertNotIn(function.name, {row.function for row in function_attendance_by_type.get_data({})})
		self.assertEqual(function_attendance_by_person.get_data({"person": self.people[0]}), [])
		inactive = {row.name: row for row in inactive_members.get_data({})}
		self.assertIsNone(inactive[self.people[0]].last_attended)

	def test_the_daily_job_counts_a_function_once_it_starts(self):
		function = make_attended_function(
			"_Test Roster Started", add_days(today(), 1), self.people, "Assumed"
		)
		frappe.db.set_value("Function", function.name, "start_date", add_days(today(), -1))

		with patch.object(frappe.db, "commit"):
			refresh_started_totals()

		self.assertEqual(frappe.db.get_value("Function", function.name, "attendance_total"), 3)

	def test_signed_up_and_absent_rows_never_count(self):
		visitors = [make_person(f"_Test Visitor {number}", membership="Visitor").name for number in (1, 2)]
		yesterday = add_days(today(), -1)
		signed_up = make_attended_function("_Test Signed Up", yesterday, visitors[:1], "Signed-Up")
		absent = make_attended_function("_Test Absent", yesterday, visitors[1:], "Absent")

		self.assertEqual((signed_up.attendance_total, absent.attendance_total), (0, 0))
		rows = {row.name: row for row in visitor_log.get_data({})}
		for visitor in visitors:
			self.assertEqual(rows[visitor].visit_count, 0)
			self.assertIsNone(rows[visitor].first_visit)

	def test_the_patch_zeroes_future_totals_and_can_run_again(self):
		future = make_attended_function("_Test Roster Patched", add_days(today(), 1), self.people, "Assumed")
		past = make_attended_function("_Test Roster Kept", today(), self.people, "Assumed")
		frappe.db.set_value("Function", future.name, "attendance_total", 3)

		zero_future_attendance_totals.execute()
		zero_future_attendance_totals.execute()

		self.assertEqual(frappe.db.get_value("Function", future.name, "attendance_total"), 0)
		self.assertEqual(frappe.db.get_value("Function", past.name, "attendance_total"), 3)


class TestAttendanceWriters(FrappeTestCase):
	"""`record` and `remove` are the only writers of a person's attendance row."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.first, cls.second = (make_person("_Test Writer", name).name for name in ("First", "Second"))

	def setUp(self):
		self.function = make_function(
			"_Test Writers", start_date=add_days(today(), -1), allow_sign_ups=1
		).name

	def _types(self):
		rows = frappe.get_doc("Function", self.function).attendance
		return {row.person: row.attendance_type for row in rows}

	def _sign_up(self, person):
		return frappe.new_doc("Function Sign-Up", function=self.function, person=person).insert(
			ignore_permissions=True
		)

	def test_record_and_remove_lock_the_function_row(self):
		with patch.object(frappe, "get_doc", wraps=frappe.get_doc) as get_doc:
			self.assertTrue(record(self.first, self.function, "Confirmed"))
			get_doc.assert_any_call("Function", self.function, for_update=True)
			get_doc.reset_mock()
			self.assertTrue(remove(self.first, self.function, "Confirmed"))
			get_doc.assert_any_call("Function", self.function, for_update=True)

	def test_a_type_is_raised_by_rank_and_never_lowered(self):
		record(self.first, self.function, "Signed-Up")
		self.assertTrue(record(self.first, self.function, "Confirmed"))
		self.assertTrue(record(self.first, self.function, "Absent"))
		self.assertFalse(record(self.first, self.function, "Assumed"))
		self.assertFalse(record(self.first, self.function, "Absent"))
		self.assertEqual(self._types(), {self.first: "Absent"})

	def test_a_sign_up_leaves_a_check_in_and_an_absence(self):
		record(self.first, self.function, "Checked-In")
		record(self.second, self.function, "Absent")

		self._sign_up(self.first)
		self._sign_up(self.second)

		self.assertEqual(self._types(), {self.first: "Checked-In", self.second: "Absent"})

	def test_deleting_a_sign_up_removes_only_a_signed_up_row(self):
		signed_up = self._sign_up(self.first)
		checked_in = self._sign_up(self.second)
		record(self.second, self.function, "Checked-In")

		signed_up.delete(ignore_permissions=True)
		checked_in.delete(ignore_permissions=True)

		self.assertEqual(self._types(), {self.second: "Checked-In"})
		self.assertFalse(remove(self.second, self.function, "Signed-Up"))

	def test_a_stale_desk_save_after_record_is_refused(self):
		desk_copy = frappe.get_doc("Function", self.function)
		record(self.first, self.function, "Checked-In")

		desk_copy.description = "Edited in an open form"
		with self.assertRaises(frappe.TimestampMismatchError):
			desk_copy.save(ignore_permissions=True)

	def test_checking_in_two_people_counts_both_on_a_past_function(self):
		check_in_persons(self.function, [self.first, self.second])

		self.assertEqual(frappe.db.get_value("Function", self.function, "attendance_total"), 2)

	def test_a_change_refreshes_the_persons_summaries(self):
		queued = queued_people(lambda: record(self.first, self.function, "Confirmed"))

		self.assertEqual(queued, [[self.first]])

	def test_record_saves_a_function_that_holds_a_value_a_later_check_refuses(self):
		"""A later Function.validate check acts only when its own field changes, as the R1 contract says."""

		def refuse_a_cancelled_description(function):
			if function.has_value_changed("description") and function.description == "Cancelled":
				frappe.throw("Refused")

		frappe.db.set_value("Function", self.function, "description", "Cancelled")
		with patch.object(Function, "validate", refuse_a_cancelled_description, create=True):
			with self.assertRaises(frappe.ValidationError):
				make_function("_Test Writers Refused", description="Cancelled")
			self.assertTrue(record(self.first, self.function, "Checked-In"))

		self.assertEqual(self._types(), {self.first: "Checked-In"})


class TestHeadcount(FrappeTestCase):
	"""The attendance total is the larger of the station headcount and the named count."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.people = [make_person("_Test Headcount", str(number)).name for number in range(13)]

	def setUp(self):
		self.function = make_attended_function(
			"_Test Headcount", add_days(today(), -1), self.people[:12], "Checked-In"
		).name

	def tearDown(self):
		frappe.set_user("Administrator")

	def _total(self):
		return frappe.db.get_value("Function", self.function, "attendance_total")

	def test_the_larger_of_headcount_and_named_count_is_the_total(self):
		self.assertEqual(set_headcount(self.function, 40), 40)
		self.assertEqual(
			frappe.db.get_value("Function", self.function, ["headcount", "attendance_total"]), (40, 40)
		)

		self.assertEqual(set_headcount(self.function, 5), 12)
		self.assertEqual(self._total(), 12)

	def test_a_negative_or_future_headcount_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			set_headcount(self.function, -1)

		future = make_function("_Test Headcount Ahead", start_date=add_days(today(), 1)).name
		with self.assertRaises(frappe.ValidationError):
			set_headcount(future, 10)
		self.assertEqual(frappe.db.get_value("Function", future, "headcount"), 0)

	def test_a_later_record_keeps_the_headcount_rule(self):
		set_headcount(self.function, 40)
		record(self.people[12], self.function, "Checked-In")
		self.assertEqual(self._total(), 40)

		set_headcount(self.function, 5)
		remove(self.people[12], self.function, "Checked-In")
		self.assertEqual(self._total(), 12)

	def test_the_daily_job_keeps_the_headcount(self):
		frappe.db.set_value("Function", self.function, {"headcount": 40, "attendance_total": 0})

		with patch.object(frappe.db, "commit") as commit:
			refresh_started_totals()

		self.assertTrue(commit.called)

		self.assertEqual(self._total(), 40)

	def test_a_desk_save_counts_the_headcount_only_once_the_function_starts(self):
		function = frappe.get_doc("Function", self.function)
		function.headcount = 40
		function.save(ignore_permissions=True)
		self.assertEqual(function.attendance_total, 40)

		ahead = make_function("_Test Headcount Ahead", start_date=add_days(today(), 1), headcount=40)
		self.assertEqual(ahead.attendance_total, 0)

	def test_only_a_check_in_user_of_the_functions_church_sets_it(self):
		ensure_root_church()
		set_multi_church(True)
		self.addCleanup(frappe.clear_cache)
		branch_a = make_branch("_Test Headcount A", "THCA")
		branch_b = make_branch("_Test Headcount B", "THCB")
		service = make_function("_Test Headcount A", church=branch_a, start_date=today()).name
		volunteer_a = self._bind("_test_headcount_a@example.com", ("Church Check-In",), branch_a)
		volunteer_b = self._bind("_test_headcount_b@example.com", ("Church Check-In",), branch_b)
		member_a = self._bind("_test_headcount_member@example.com", ("Church User",), branch_a)

		for user in (volunteer_b, member_a):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				set_headcount(service, 30)

		frappe.set_user(volunteer_a)
		self.assertEqual(set_headcount(service, 30), 30)

	def _bind(self, email, roles, church):
		user = ensure_user(email, email.split("@")[0], roles=roles)
		if not frappe.db.exists("Person", {"user": user}):
			make_person(email.split("@")[0], "_Test Headcount User", church=church, user=user)
		return user
