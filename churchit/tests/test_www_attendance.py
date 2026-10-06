# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member-facing /attendance page: a member sees their own attendance and no one else's."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate

from churchit.church_ministries.member_attendance import change_own_attendance
from churchit.tests.helpers import ensure_user, make_function, make_person
from churchit.www.attendance import get_context


class AttendanceTestCase(FrappeTestCase):
	"""A portal member and a stranger, with Portal Settings set by each test class."""

	members_can_change_attendance = 0

	def setUp(self):
		frappe.local.form_dict = frappe._dict()
		frappe.db.set_single_value(
			"Portal Settings", "members_can_change_attendance", self.members_can_change_attendance
		)
		self.email = ensure_user("_test_attendance_member@example.com", "Attendance")
		self.person = make_person("_Test Portal", "Attender", user=self.email)
		self.stranger = make_person("_Test Portal", "Stranger")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _function(self, days_from_today, attendance):
		return make_function(
			"_Test Attendance Function",
			start_date=add_days(getdate(), days_from_today),
			attendance=[{"person": person, "attendance_type": status} for person, status in attendance],
		)

	def _context(self):
		context = frappe._dict()
		get_context(context)
		return context

	def _listed(self):
		return {row.name: row for row in self._context().attendance}


class TestAttendancePage(AttendanceTestCase):
	def test_guests_are_sent_to_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			self._context()

	def test_member_sees_their_own_attendance_with_its_status(self):
		function = self._function(-7, [(self.person.name, "Checked-In")])
		frappe.set_user(self.email)

		self.assertEqual(self._listed()[function.name].attendance_type, "Checked-In")

	def test_member_does_not_see_another_persons_attendance(self):
		theirs = self._function(-7, [(self.stranger.name, "Checked-In")])
		frappe.set_user(self.email)

		self.assertNotIn(theirs.name, self._listed())

	def test_newest_function_comes_first(self):
		older = self._function(-14, [(self.person.name, "Confirmed")])
		newer = self._function(-1, [(self.person.name, "Confirmed")])
		frappe.set_user(self.email)

		names = list(self._listed())

		self.assertLess(names.index(newer.name), names.index(older.name))

	def test_a_function_that_has_not_happened_is_not_listed(self):
		"""A recurring function copies its roster onto the next occurrence before it happens."""
		upcoming = self._function(7, [(self.person.name, "Assumed")])
		frappe.set_user(self.email)

		self.assertNotIn(upcoming.name, self._listed())

	def test_user_without_a_person_record_gets_an_empty_list(self):
		frappe.set_user(ensure_user("_test_attendance_nobody@example.com", "Nobody"))

		context = self._context()

		self.assertIsNone(context.person)
		self.assertEqual(context.attendance, [])

	def test_nothing_can_be_changed_until_portal_settings_allows_it(self):
		function = self._function(-7, [(self.person.name, "Assumed")])
		frappe.set_user(self.email)

		self.assertFalse(self._listed()[function.name].is_changeable)
		with self.assertRaises(frappe.PermissionError):
			change_own_attendance(function.name, "Absent")


class TestChangingOwnAttendance(AttendanceTestCase):
	"""Portal Settings lets members correct their own attendance, and nothing more."""

	members_can_change_attendance = 1

	def _attendance(self, function):
		rows = frappe.get_doc("Function", function).attendance
		return [row.attendance_type for row in rows if row.person == self.person.name]

	def test_member_corrects_a_sign_up_to_confirmed_and_it_counts(self):
		function = self._function(-7, [(self.person.name, "Signed-Up")])
		frappe.set_user(self.email)

		self.assertTrue(self._listed()[function.name].is_changeable)
		change_own_attendance(function.name, "Confirmed")

		self.assertEqual(self._attendance(function.name), ["Confirmed"])
		self.assertEqual(frappe.db.get_value("Function", function.name, "attendance_total"), 1)

	def test_a_check_in_cannot_be_changed(self):
		function = self._function(-7, [(self.person.name, "Checked-In")])
		frappe.set_user(self.email)

		self.assertFalse(self._listed()[function.name].is_changeable)
		with self.assertRaises(frappe.PermissionError):
			change_own_attendance(function.name, "Absent")

	def test_only_confirmed_or_absent_may_be_chosen(self):
		function = self._function(-7, [(self.person.name, "Assumed")])
		frappe.set_user(self.email)

		with self.assertRaises(frappe.PermissionError):
			change_own_attendance(function.name, "Checked-In")

	def test_a_function_the_page_does_not_list_cannot_be_changed(self):
		theirs = self._function(-7, [(self.stranger.name, "Assumed")])
		upcoming = self._function(7, [(self.person.name, "Assumed")])
		frappe.set_user(self.email)

		for function in (theirs, upcoming):
			with self.assertRaises(frappe.PermissionError):
				change_own_attendance(function.name, "Absent")
		self.assertEqual(self._attendance(upcoming.name), ["Assumed"])
