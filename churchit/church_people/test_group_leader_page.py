# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The /group-leader page: a leader's roster, the attendance they record, and the reminder to record it."""

from unittest import mock

import frappe
from frappe.handler import execute_cmd
from frappe.utils import add_days, getdate, set_request
from frappe.website.serve import get_response

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	GROUP_MESSAGES,
	create_communication_purposes,
)
from churchit.church_people.group_meetings import (
	get_group_meetings,
	record_group_attendance,
	send_attendance_reminders,
)
from churchit.patches.after_install import create_unsynced_records
from churchit.patches.v1_0 import add_group_leader_menu_item
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_function, make_person
from churchit.www.group_leader import get_context

LEADER_ROLE = "_Test Page Leader"
MEMBER_ROLE = "_Test Page Member"


class GroupLeaderTestCase(RollbackEachTest):
	"""A group with a leader, two living members and one who died, and a second group with its own leader."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_communication_purposes()
		create_unsynced_records()
		ensure("Group Role", {"role": LEADER_ROLE}, {"role": LEADER_ROLE, "is_leader": 1})
		ensure("Group Role", {"role": MEMBER_ROLE}, {"role": MEMBER_ROLE, "is_leader": 0})
		cls.leader_user = ensure_user("_test_page_leader@example.com", "_Test Page Leader")
		cls.leader = make_person(
			"Lee",
			"_Test Page",
			user=cls.leader_user,
			emails=[{"email_address": "_test_page_leader@example.com"}],
		)
		cls.sharer = make_person(
			"Sam",
			"_Test Page",
			share_email=1,
			share_phone=1,
			emails=[{"email_address": "_test_page_sharer@example.com"}],
			phones=[{"phone_number": "555 010 0151"}],
		)
		cls.private = make_person(
			"Pat",
			"_Test Page",
			share_email=0,
			share_phone=0,
			emails=[{"email_address": "_test_page_private@example.com"}],
			phones=[{"phone_number": "555 010 0152"}],
		)
		cls.departed = make_person("Dan", "_Test Page")
		frappe.db.set_value("Person", cls.departed.name, "is_deceased", 1)
		cls.outsider = make_person("Oz", "_Test Page")
		cls.group = cls.make_group(
			"_Test Page Group",
			[
				(cls.leader, LEADER_ROLE),
				(cls.sharer, MEMBER_ROLE),
				(cls.private, MEMBER_ROLE),
				(cls.departed, MEMBER_ROLE),
			],
		)

		cls.other_leader_user = ensure_user("_test_page_other_leader@example.com", "_Test Page Other")
		cls.other_leader = make_person(
			"Ola",
			"_Test Page",
			user=cls.other_leader_user,
			emails=[{"email_address": "_test_page_other_leader@example.com"}],
		)
		cls.other_group = cls.make_group("_Test Page Other Group", [(cls.other_leader, LEADER_ROLE)])
		record([cls.leader.name, cls.other_leader.name, cls.sharer.name], EMAIL, GIVEN, GROUP_MESSAGES)

	@classmethod
	def make_group(cls, name, members):
		group = frappe.get_doc({"doctype": "Group", "group_name": name})
		for person, role in members:
			group.append("members", {"person": person.name, "group_role": role})
		return group.insert(ignore_permissions=True)

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())

	def meeting(self, days_from_today=-1, group=None, **values):
		return make_function(
			"_Test Page Meeting",
			group=(group or self.group).name,
			start_date=add_days(getdate(), days_from_today),
			**values,
		)


class TestGroupLeaderPage(GroupLeaderTestCase):
	def context(self, user=None, **form):
		frappe.set_user(user or self.leader_user)
		frappe.local.form_dict = frappe._dict(form)
		context = frappe._dict()
		get_context(context)
		return context

	def test_a_guest_is_sent_to_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			get_context(frappe._dict())
		self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/group-leader")

	def test_the_leader_sees_the_living_members_and_only_the_contact_details_they_share(self):
		context = self.context()

		self.assertEqual(context.groups, [self.group.name])
		roster = {row.name: row for row in context.rosters[self.group.name]}
		self.assertEqual(set(roster), {self.leader.name, self.sharer.name, self.private.name})
		self.assertEqual(roster[self.sharer.name].group_role, MEMBER_ROLE)
		self.assertEqual(roster[self.sharer.name].email, "_test_page_sharer@example.com")
		self.assertEqual(roster[self.sharer.name].phone, "555 010 0151")
		self.assertIsNone(roster[self.private.name].email)
		self.assertIsNone(roster[self.private.name].phone)

	def test_the_page_lists_the_meetings_of_the_last_eight_weeks(self):
		recent = self.meeting(-1)
		old = self.meeting(-60)
		upcoming = self.meeting(3)

		listed = [meeting.name for meeting in self.context().meetings[self.group.name]]

		self.assertIn(recent.name, listed)
		self.assertNotIn(old.name, listed)
		self.assertNotIn(upcoming.name, listed)

	def test_a_member_who_leads_nothing_sees_no_group(self):
		member_user = ensure_user("_test_page_member@example.com", "_Test Page Member")
		frappe.db.set_value("Person", self.sharer.name, "user", member_user)

		self.assertEqual(self.context(member_user).groups, [])

	def test_the_group_in_the_link_narrows_the_page_to_that_group(self):
		second = self.make_group("_Test Page Second Group", [(self.leader, LEADER_ROLE)])
		self.assertEqual(set(self.context().groups), {self.group.name, second.name})

		self.assertEqual(self.context(group=second.name).groups, [second.name])
		self.assertEqual(len(self.context(group=self.other_group.name).groups), 2, "a group they do not lead")

	def test_the_page_renders_the_roster_a_meeting_and_the_message_form(self):
		meeting = self.meeting(attendance=[{"person": self.sharer.name, "attendance_type": "Confirmed"}])
		frappe.set_user(self.leader_user)
		set_request(method="GET", path="group-leader")

		html = get_response("group-leader").get_data(as_text=True)

		self.assertIn("_Test Page Group", html)
		self.assertIn("_test_page_sharer@example.com", html)
		self.assertNotIn("_test_page_private@example.com", html)
		self.assertIn(f'data-function="{meeting.name}"', html)
		self.assertRegex(html, rf'value="present" data-person="{self.sharer.name}"\s+checked>')
		self.assertIn("message-form", html)

	def test_get_group_meetings_refuses_a_leader_of_another_group(self):
		frappe.set_user(self.other_leader_user)
		with self.assertRaises(frappe.PermissionError):
			get_group_meetings(self.group.name)

	def test_the_menu_row_patch_adds_lead_a_group_once(self):
		settings = frappe.get_doc("Portal Settings")
		settings.menu = [row for row in settings.menu if row.route != add_group_leader_menu_item.ROUTE]
		settings.save(ignore_permissions=True)

		add_group_leader_menu_item.execute()
		add_group_leader_menu_item.execute()

		rows = [
			row
			for row in frappe.get_doc("Portal Settings").menu
			if row.route == add_group_leader_menu_item.ROUTE
		]
		self.assertEqual(len(rows), 1)
		self.assertEqual((rows[0].title, rows[0].role), ("Lead a Group", "Church User"))


class TestRecordGroupAttendance(GroupLeaderTestCase):
	def record(self, meeting, user=None, **kwargs):
		frappe.set_user(user or self.leader_user)
		try:
			record_group_attendance(meeting.name, **kwargs)
		finally:
			frappe.set_user("Administrator")
		return frappe.get_doc("Function", meeting.name)

	def statuses(self, meeting):
		return {row.person: row.attendance_type for row in meeting.attendance}

	def comments(self, meeting):
		return frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Function", "reference_name": meeting.name},
			pluck="content",
		)

	def test_present_and_absent_write_confirmed_and_absent_rows_that_count(self):
		meeting = self.record(self.meeting(), present=[self.sharer.name], absent=[self.private.name])

		self.assertEqual(self.statuses(meeting), {self.sharer.name: "Confirmed", self.private.name: "Absent"})
		self.assertEqual(meeting.attendance_total, 1)
		self.assertTrue(meeting.attendance_recorded_on)
		self.assertFalse(meeting.did_not_meet)

	def test_one_save_adds_one_comment_that_names_the_leader(self):
		meeting = self.record(self.meeting(), present=[self.sharer.name, self.private.name])

		[comment] = self.comments(meeting)
		self.assertIn("Lee _Test Page", comment)

	def test_a_check_in_stays_a_check_in(self):
		meeting = self.meeting(attendance=[{"person": self.sharer.name, "attendance_type": "Checked-In"}])

		meeting = self.record(meeting, present=[self.sharer.name])

		self.assertEqual(self.statuses(meeting), {self.sharer.name: "Checked-In"})

	def test_a_leader_of_another_group_is_refused(self):
		meeting = self.meeting()

		with self.assertRaises(frappe.PermissionError):
			self.record(meeting, user=self.other_leader_user, present=[self.sharer.name])
		self.assertEqual(self.statuses(frappe.get_doc("Function", meeting.name)), {})

	def test_a_meeting_of_no_group_is_refused(self):
		meeting = make_function("_Test Page Not A Meeting", start_date=add_days(getdate(), -1))

		with self.assertRaises(frappe.PermissionError):
			self.record(meeting, present=[self.sharer.name])

	def test_a_person_outside_the_group_is_refused(self):
		meeting = self.meeting()

		with self.assertRaises(frappe.ValidationError):
			self.record(meeting, present=[self.outsider.name])
		self.assertEqual(self.statuses(frappe.get_doc("Function", meeting.name)), {})

	def test_a_person_already_on_the_attendance_can_be_marked(self):
		meeting = self.meeting(attendance=[{"person": self.outsider.name, "attendance_type": "Signed-Up"}])

		meeting = self.record(meeting, present=[self.outsider.name])

		self.assertEqual(self.statuses(meeting), {self.outsider.name: "Confirmed"})

	def test_the_groups_schedule_takes_no_attendance(self):
		"""Each occurrence copies its template's attendance, so the template keeps none."""
		template = self.meeting(auto_repeat=1, repeat_frequency="Weekly")

		with self.assertRaises(frappe.ValidationError):
			self.record(template, present=[self.sharer.name])

	def test_did_not_meet_writes_no_rows(self):
		meeting = self.record(self.meeting(), present=[self.sharer.name], did_not_meet="1")

		self.assertEqual(self.statuses(meeting), {})
		self.assertEqual(meeting.did_not_meet, 1)
		self.assertTrue(meeting.attendance_recorded_on)
		self.assertEqual(len(self.comments(meeting)), 1)

	def test_a_get_is_refused(self):
		"""A GET carries no CSRF token, so another site could record attendance in a leader's browser."""
		meeting = self.meeting()
		frappe.set_user(self.leader_user)
		frappe.local.request = frappe._dict(method="GET")
		self.addCleanup(delattr, frappe.local, "request")
		frappe.local.form_dict = frappe._dict(
			function=meeting.name, present=frappe.as_json([self.sharer.name])
		)

		with self.assertRaises(frappe.PermissionError):
			execute_cmd("churchit.church_people.group_meetings.record_group_attendance")
		self.assertEqual(self.statuses(frappe.get_doc("Function", meeting.name)), {})


class TestAttendanceReminders(GroupLeaderTestCase):
	def setUp(self):
		super().setUp()
		self.sendmail = mock.patch("frappe.sendmail").start()
		mock.patch("churchit.church_people.group_meetings.can_send_email", return_value=True).start()
		self.addCleanup(mock.patch.stopall)

	def reminders(self, meeting):
		"""The leaders reminded about *meeting*."""
		names = frappe.get_all(
			"Communication Link",
			filters={"link_doctype": "Function", "link_name": meeting.name, "parenttype": "Communication"},
			pluck="parent",
		)
		return frappe.get_all(
			"Communication",
			filters={"name": ("in", names), "send_key": "attendance-reminder"},
			pluck="reference_name",
		)

	def test_a_meeting_yesterday_reminds_each_leader_once(self):
		meeting = self.meeting()

		send_attendance_reminders()
		send_attendance_reminders()

		self.assertEqual(self.reminders(meeting), [self.leader.name])
		[email] = [
			call.kwargs
			for call in self.sendmail.call_args_list
			if call.kwargs["reference_name"] == meeting.name
		]
		self.assertEqual(email["recipients"], ["_test_page_leader@example.com"])
		self.assertIn(f"/group-leader?group={self.group.name}", email["message"])

	def test_a_meeting_of_a_group_with_no_leader_does_not_stop_the_other_reminders(self):
		leaderless = self.make_group("_Test Page Leaderless Group", [(self.sharer, MEMBER_ROLE)])
		skipped = self.meeting(group=leaderless)
		meeting = self.meeting()

		send_attendance_reminders()

		self.assertEqual(self.reminders(skipped), [])
		self.assertEqual(self.reminders(meeting), [self.leader.name])

	def test_a_recorded_a_cancelled_or_an_older_meeting_reminds_no_one(self):
		recorded = self.meeting()
		frappe.db.set_value("Function", recorded.name, "attendance_recorded_on", frappe.utils.now_datetime())
		cancelled = self.meeting(did_not_meet=1)
		older = self.meeting(-2)

		send_attendance_reminders()

		for meeting in (recorded, cancelled, older):
			self.assertEqual(self.reminders(meeting), [], meeting.name)

	def test_nothing_is_sent_while_the_site_has_no_outgoing_email_account(self):
		meeting = self.meeting()

		with mock.patch("churchit.church_people.group_meetings.can_send_email", return_value=False):
			send_attendance_reminders()

		self.assertEqual(self.reminders(meeting), [])

	def test_a_leader_who_withdrew_group_messages_gets_no_reminder(self):
		record([self.leader.name], EMAIL, WITHDRAWN, GROUP_MESSAGES)
		meeting = self.meeting()

		send_attendance_reminders()

		self.assertEqual(self.reminders(meeting), [])
