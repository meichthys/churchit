# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A member's own attendance: what is listed, and what they may correct."""

import frappe
from frappe.utils import add_days, getdate

from churchit.church_ministries.member_attendance import (
	change_own_attendance,
	get_own_attendance,
	get_upcoming_sign_ups,
)
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_function, make_person


class MemberAttendanceTestCase(RollbackEachTest):
	"""A portal member and a stranger, with Portal Settings set by each test class."""

	members_can_change_attendance = 0

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.set_single_value(
			"Portal Settings", "members_can_change_attendance", cls.members_can_change_attendance
		)
		cls.email = ensure_user("_test_attendance_member@example.com", "Attendance")
		cls.person = make_person("_Test Portal", "Attender", user=cls.email)
		cls.stranger = make_person("_Test Portal", "Stranger")

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()

	def _function(self, days_from_today, attendance):
		return make_function(
			"_Test Attendance Function",
			start_date=add_days(getdate(), days_from_today),
			attendance=[{"person": person, "attendance_type": status} for person, status in attendance],
		)

	def _listed(self):
		return {row.name: row for row in get_own_attendance(self.person.name)}

	def _signed_up(self, days_from_today, person):
		"""A function *days_from_today* days from today, with a sign-up for *person*."""
		function = make_function(
			"_Test Attendance Camp", start_date=add_days(getdate(), days_from_today), allow_sign_ups=1
		)
		frappe.get_doc({"doctype": "Function Sign-Up", "function": function.name, "person": person}).insert(
			ignore_permissions=True
		)
		return function


class TestOwnAttendance(MemberAttendanceTestCase):
	def test_member_sees_their_own_attendance_with_its_status(self):
		function = self._function(-7, [(self.person.name, "Checked-In")])

		self.assertEqual(self._listed()[function.name].attendance_type, "Checked-In")

	def test_member_does_not_see_another_persons_attendance(self):
		theirs = self._function(-7, [(self.stranger.name, "Checked-In")])

		self.assertNotIn(theirs.name, self._listed())

	def test_newest_function_comes_first(self):
		older = self._function(-14, [(self.person.name, "Confirmed")])
		newer = self._function(-1, [(self.person.name, "Confirmed")])

		names = list(self._listed())

		self.assertLess(names.index(newer.name), names.index(older.name))

	def test_a_function_that_has_not_happened_is_not_listed(self):
		"""A recurring function copies its roster onto the next occurrence before it happens."""
		upcoming = self._function(7, [(self.person.name, "Assumed")])

		self.assertNotIn(upcoming.name, self._listed())

	def test_upcoming_functions_the_member_signed_up_for_are_listed_soonest_first(self):
		later = self._signed_up(14, self.person.name)
		sooner = self._signed_up(7, self.person.name)
		self._signed_up(7, self.stranger.name)
		self._signed_up(-7, self.person.name)

		upcoming = [row.name for row in get_upcoming_sign_ups(self.person.name)]

		self.assertEqual(upcoming, [sooner.name, later.name])

	def test_a_sign_up_that_waits_is_upcoming_with_its_status(self):
		booked = self._signed_up(7, self.person.name)
		full = make_function(
			"_Test Attendance Full", start_date=add_days(getdate(), 8), allow_sign_ups=1, capacity=1
		)
		for person in (self.stranger.name, self.person.name):
			frappe.get_doc({"doctype": "Function Sign-Up", "function": full.name, "person": person}).insert(
				ignore_permissions=True
			)
		cancelled = self._signed_up(9, self.person.name)
		frappe.get_doc("Function Sign-Up", {"function": cancelled.name}).cancel_registration()

		upcoming = {row.name: row.status for row in get_upcoming_sign_ups(self.person.name)}

		self.assertEqual(upcoming, {booked.name: "Confirmed", full.name: "Waitlisted"})

	def test_a_signed_up_row_without_a_sign_up_is_not_upcoming(self):
		"""A recurring function copies its template's attendance, Signed-Up rows included."""
		self._function(7, [(self.person.name, "Signed-Up")])

		self.assertEqual(get_upcoming_sign_ups(self.person.name), [])

	def test_nothing_can_be_changed_until_portal_settings_allows_it(self):
		function = self._function(-7, [(self.person.name, "Assumed")])
		frappe.set_user(self.email)

		with self.assertRaises(frappe.PermissionError):
			change_own_attendance(function.name, "Absent")


class TestChangingOwnAttendance(MemberAttendanceTestCase):
	"""Portal Settings lets members correct their own attendance, and nothing more."""

	members_can_change_attendance = 1

	def _attendance(self, function):
		rows = frappe.get_doc("Function", function).attendance
		return [row.attendance_type for row in rows if row.person == self.person.name]

	def test_member_corrects_a_sign_up_to_confirmed_and_it_counts(self):
		function = self._function(-7, [(self.person.name, "Signed-Up")])
		frappe.set_user(self.email)

		change_own_attendance(function.name, "Confirmed")

		self.assertEqual(self._attendance(function.name), ["Confirmed"])
		self.assertEqual(frappe.db.get_value("Function", function.name, "attendance_total"), 1)

	def test_a_check_in_cannot_be_changed(self):
		function = self._function(-7, [(self.person.name, "Checked-In")])
		frappe.set_user(self.email)

		with self.assertRaises(frappe.PermissionError):
			change_own_attendance(function.name, "Absent")

	def test_only_confirmed_or_absent_may_be_chosen(self):
		function = self._function(-7, [(self.person.name, "Assumed")])
		frappe.set_user(self.email)

		with self.assertRaises(frappe.PermissionError):
			change_own_attendance(function.name, "Checked-In")

	def test_a_function_the_member_has_no_past_attendance_in_cannot_be_changed(self):
		theirs = self._function(-7, [(self.stranger.name, "Assumed")])
		upcoming = self._function(7, [(self.person.name, "Assumed")])
		frappe.set_user(self.email)

		for function in (theirs, upcoming):
			with self.assertRaises(frappe.PermissionError):
				change_own_attendance(function.name, "Absent")
		self.assertEqual(self._attendance(upcoming.name), ["Assumed"])
