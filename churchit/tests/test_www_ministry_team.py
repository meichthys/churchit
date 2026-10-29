# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The /ministry-team portal page and the /ministry-team-response page a request email links to."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import add_days, get_system_timezone, getdate

from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries.member_ministry_team import (
	add_own_block,
	answer_by_key,
	answer_own_assignment,
	get_team_calendar,
	make_own_calendar_key,
	remove_own_block,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
	make_two_churches,
)
from churchit.tests.test_ics import request_feed, unfold
from churchit.www import ministry_team, ministry_team_response


class TestMinistryTeamPages(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.email = ensure_user("_test_team_member@example.com", "Team")
		cls.member = make_person("_Test Team Page", "Member", user=cls.email)
		cls.stranger = make_person("_Test Team Page", "Stranger")
		cls.position = make_team_position("_Test Page Greeter", [cls.member.name, cls.stranger.name])
		function = make_function("_Test Team Page Sunday", start_date=add_days(getdate(), 5))
		cls.mine = make_team_assignment(function.name, cls.position.name, cls.member.name)
		cls.theirs = make_team_assignment(function.name, cls.position.name, cls.stranger.name)

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()

	def context(self, page):
		context = frappe._dict()
		page.get_context(context)
		return context

	def status(self, assignment):
		return frappe.db.get_value("Ministry Team Assignment", assignment.name, "status")

	def test_guests_are_sent_to_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			self.context(ministry_team)

	def test_a_member_sees_only_their_own_assignments(self):
		frappe.set_user(self.email)
		listed = [row.name for row in self.context(ministry_team).assignments]
		self.assertEqual(listed, [self.mine.name])

	def test_a_function_stays_listed_until_it_ends(self):
		today = getdate()
		retreat = make_function(
			"_Test Team Page Retreat", start_date=add_days(today, -1), end_date=add_days(today, 1)
		)
		ended = make_function(
			"_Test Team Page Past", start_date=add_days(today, -3), end_date=add_days(today, -1)
		)
		running = make_team_assignment(retreat.name, self.position.name, self.member.name)
		make_team_assignment(ended.name, self.position.name, self.member.name)

		frappe.set_user(self.email)
		listed = {row.name: row.has_started for row in self.context(ministry_team).assignments}
		self.assertEqual(listed, {running.name: True, self.mine.name: False})

	def test_a_member_sees_the_schedule_of_each_function_they_serve_at(self):
		song = frappe.get_doc({"doctype": "Song", "title": "_Test Team Page Hymn"}).insert(
			ignore_permissions=True
		)
		start = f"{add_days(getdate(), 6)} 10:00:00"
		function = make_function(
			"_Test Team Page Schedule",
			start_date=add_days(getdate(), 6),
			schedule=[
				{"start": start, "description": "Welcome"},
				{"start": start, "item_type": "Song", "item": song.name, "description": "Everyone stands"},
			],
		)
		make_team_assignment(function.name, self.position.name, self.member.name)

		frappe.set_user(self.email)
		schedules = self.context(ministry_team).schedules
		self.assertEqual(
			[(row.time, row.title, row.detail) for row in schedules[function.name].rows],
			[("10:00 AM", "Welcome", None), ("10:00 AM", "_Test Team Page Hymn", "Everyone stands")],
		)
		self.assertEqual(schedules[self.mine.function].rows, [])

	def test_a_member_answers_their_own_assignment_and_no_one_elses(self):
		frappe.set_user(self.email)
		answer_own_assignment(self.mine.name, "Declined", "Away")
		with self.assertRaises(frappe.PermissionError):
			answer_own_assignment(self.theirs.name, "Declined")

		frappe.set_user("Administrator")
		self.assertEqual(self.status(self.mine), "Declined")
		self.assertEqual(self.status(self.theirs), "Pending")

	def test_anyone_with_the_emailed_link_can_answer_it(self):
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(key=self.theirs.response_key)
		self.assertEqual(self.context(ministry_team_response).request.first_name, "_Test Team Page")

		answer_by_key(self.theirs.response_key, "Accepted")

		frappe.set_user("Administrator")
		self.assertEqual(self.status(self.theirs), "Accepted")

	def test_a_wrong_key_answers_nothing(self):
		frappe.set_user("Guest")
		for key in ("", "not-a-key"):
			frappe.local.form_dict = frappe._dict(key=key)
			with self.assertRaises(frappe.PermissionError):
				self.context(ministry_team_response)
			with self.assertRaises(frappe.PermissionError):
				answer_by_key(key, "Accepted")

	def test_a_member_adds_and_removes_their_own_blocks(self):
		frappe.set_user(self.email)
		add_own_block(str(add_days(getdate(), 1)), str(add_days(getdate(), 3)), "Away", "1")
		[block] = self.context(ministry_team).blocks
		self.assertEqual((block.reason, block.whole_household), ("Away", 1))

		remove_own_block(block.name)
		self.assertEqual(self.context(ministry_team).blocks, [])

	def calendar(self, key, etag=None):
		frappe.set_user("Guest")
		return request_feed(self, get_team_calendar, etag=etag, key=key)

	def test_a_member_subscribes_to_a_calendar_of_what_they_accepted(self):
		day = add_days(getdate(), 8)
		accepted = make_function(
			"_Test Team Page Accepted", start_date=day, start_time="09:30:00", end_time="11:00:00"
		)
		make_team_assignment(accepted.name, self.position.name, self.member.name, status="Accepted")

		frappe.set_user(self.email)
		self.assertIsNone(self.context(ministry_team).calendar)
		make_own_calendar_key()
		calendar = self.context(ministry_team).calendar
		key = calendar.url.partition("key=")[2]
		self.assertTrue(calendar.webcal.startswith("webcal://"))

		response = self.calendar(key)
		self.assertEqual(response.mimetype, "text/calendar")
		feed = unfold(response)
		start = datetime.combine(day, time(9, 30))
		utc_start = start.replace(tzinfo=ZoneInfo(get_system_timezone())).astimezone(UTC)
		self.assertIn(f"DTSTART:{utc_start:%Y%m%dT%H%M%SZ}", feed)
		self.assertIn("SUMMARY:_Test Page Greeter (_Test Team Ministry) at _Test Team Page Accepted", feed)
		self.assertNotIn("_Test Team Page Sunday", feed, "a pending assignment is not on the calendar")

	def test_a_new_calendar_link_stops_the_old_one(self):
		frappe.set_user(self.email)
		make_own_calendar_key()
		old_key = frappe.db.get_value("Person", self.member.name, "team_calendar_key")
		make_own_calendar_key()

		with self.assertRaises(frappe.PermissionError):
			self.calendar(old_key)
		with self.assertRaises(frappe.PermissionError):
			self.calendar("")

	def test_an_unchanged_team_feed_keeps_its_etag_and_answers_304(self):
		accepted = make_function("_Test Team Page Etag", start_date=add_days(getdate(), 9))
		make_team_assignment(accepted.name, self.position.name, self.member.name, status="Accepted")
		frappe.set_user(self.email)
		make_own_calendar_key()
		key = frappe.db.get_value("Person", self.member.name, "team_calendar_key")

		first = self.calendar(key)
		self.assertIn("_Test Team Page Etag", unfold(first))
		self.assertEqual(first.get_etag(), self.calendar(key).get_etag())

		cached = self.calendar(key, etag=f'"{first.get_etag()[0]}"')
		self.assertEqual(cached.status_code, 304)
		self.assertEqual(cached.get_data(), b"")

	def test_a_member_cannot_remove_someone_elses_block(self):
		theirs = frappe.get_doc(
			{
				"doctype": "Ministry Team Block",
				"person": self.stranger.name,
				"from_date": getdate(),
				"to_date": getdate(),
			}
		).insert(ignore_permissions=True)
		frappe.set_user(self.email)
		with self.assertRaises(frappe.PermissionError):
			remove_own_block(theirs.name)


class TestCalendarKeyPermission(RollbackEachTest):
	"""Only the member and System Manager reach a calendar key; staff of any church do not."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, branch_a, branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.person = make_person("_Test Calendar Key", "Holder", church=branch_a).name
		frappe.db.set_value("Person", cls.person, "team_calendar_key", "_test_calendar_key")
		cls.managers = []
		for email, church in (
			("_test_key_manager_a@example.com", branch_a),
			("_test_key_manager_b@example.com", branch_b),
		):
			cls.managers.append(ensure_user(email, "Key Manager", roles=("Church Manager",)))
			set_user_church(email, church)

	def test_staff_cannot_read_a_calendar_key(self):
		for manager in self.managers:
			frappe.set_user(manager)
			person = frappe.get_doc("Person", self.person)
			person.apply_fieldlevel_read_permissions()
			self.assertIsNone(person.get("team_calendar_key"), manager)
			rows = frappe.get_list(
				"Person", filters={"name": self.person}, fields=["name", "team_calendar_key"]
			)
			self.assertEqual([row.get("team_calendar_key") for row in rows], [None], manager)
