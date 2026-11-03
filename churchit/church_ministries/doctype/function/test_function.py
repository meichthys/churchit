# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from datetime import date, time, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, get_datetime, getdate

from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries.doctype.function.function import (
	_as_time,
	apply_template,
	get_calendar_events,
	move_on_calendar,
)
from churchit.church_ministries.recurrence import create_occurrence
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_team_position,
	make_two_churches,
)


class TestFunction(FrappeTestCase):
	def setUp(self):
		self.person = make_person("_Test Function Attendee").name

	def test_title_includes_start_date(self):
		function = make_function("_Test Titled", start_date="2031-05-01")
		self.assertEqual(function.title, "_Test Titled: 2031-05-01")

	def test_attendance_total_counts_only_present_types(self):
		function = make_function("_Test Counted", start_date=getdate())
		for attendance_type in ("Confirmed", "Assumed", "Checked-In", "Absent", "Signed-Up"):
			function.append(
				"attendance",
				{"person": make_person(f"_Test {attendance_type}").name, "attendance_type": attendance_type},
			)
		function.save(ignore_permissions=True)
		self.assertEqual(function.attendance_total, 3)

	def test_apply_template_copies_whitelisted_fields_and_tables(self):
		ministry = ensure("Ministry", {"ministry_name": "_Test Template Ministry"})
		template = make_function(
			"_Test Template",
			description="Weekly gathering",
			all_day=1,
			associated_ministry=ministry,
			publish=1,
		)
		template.append("attendance", {"person": self.person, "attendance_type": "Assumed"})
		template.save(ignore_permissions=True)

		copied = apply_template(template.name)

		self.assertEqual(copied["description"], "Weekly gathering")
		self.assertEqual(copied["all_day"], 1)
		self.assertEqual(copied["associated_ministry"], ministry)
		self.assertEqual([row["person"] for row in copied["attendance"]], [self.person])
		# Only the whitelisted fields travel: dates, publish state and name do not.
		for field in ("function_name", "start_date", "publish", "name"):
			self.assertNotIn(field, copied)

	def test_apply_template_moves_the_schedule_to_the_new_start_date(self):
		template = make_function("_Test Retreat Plan", start_date="2031-05-02", end_date="2031-05-04")
		template.append("schedule", {"description": "Opening", "start": "2031-05-02 19:00:00"})
		template.append(
			"schedule", {"description": "Hike", "start": "2031-05-03 09:00:00", "end": "2031-05-03 12:00:00"}
		)
		template.save(ignore_permissions=True)

		copied = apply_template(template.name, "2031-06-06")

		self.assertEqual(
			[(row["start"], row["end"]) for row in copied["schedule"]],
			[
				(get_datetime("2031-06-06 19:00:00"), None),
				(get_datetime("2031-06-07 09:00:00"), get_datetime("2031-06-07 12:00:00")),
			],
		)

	def test_apply_template_copies_the_team_needs(self):
		position = make_team_position("_Test Template Greeter", [self.person])
		template = make_function(
			"_Test Team Template", team_needs=[{"position": position.name, "quantity": 3}]
		)

		copied = apply_template(template.name)

		self.assertEqual(
			[(row["position"], row["quantity"]) for row in copied["team_needs"]], [(position.name, 3)]
		)

	def test_as_time_accepts_time_timedelta_and_string(self):
		self.assertEqual(_as_time(time(9, 30)), time(9, 30))
		self.assertEqual(_as_time(timedelta(hours=9, minutes=30)), time(9, 30))
		self.assertEqual(_as_time("09:30:00"), time(9, 30))


class TestFunctionGroup(RollbackEachTest):
	def make_group(self, name, **values):
		return frappe.get_doc({"doctype": "Group", "group_name": name, **values}).insert(
			ignore_permissions=True
		)

	def test_an_occurrence_keeps_the_templates_group(self):
		group = self.make_group("_Test Meeting Group")
		template = make_function(
			"_Test Group Template", group=group.name, auto_repeat=1, repeat_frequency="Weekly"
		)

		occurrence = create_occurrence(template, getdate("2031-05-08"))

		self.assertEqual(occurrence.group, group.name)

	def test_another_churches_group_is_refused(self):
		_root, church_a, church_b = make_two_churches()
		group = self.make_group("_Test Church B Group", church=church_b)

		with self.assertRaises(frappe.PermissionError):
			make_function("_Test Church A Meeting", church=church_a, group=group.name)

	def test_a_shared_function_cannot_have_a_group(self):
		group = self.make_group("_Test Shared Group")

		with self.assertRaises(frappe.ValidationError):
			make_function("_Test Shared Meeting", is_shared=1, group=group.name)

	def test_a_new_group_association_row_is_refused(self):
		group = self.make_group("_Test Association Group")
		function = make_function("_Test Associated Function")

		function.append("associations", {"association_type": "Group", "association": group.name})
		with self.assertRaises(frappe.ValidationError):
			function.save(ignore_permissions=True)

	def test_a_new_function_with_a_group_association_row_is_refused(self):
		group = self.make_group("_Test New Association Group")

		with self.assertRaises(frappe.ValidationError):
			make_function(
				"_Test New Associated Function",
				associations=[{"association_type": "Group", "association": group.name}],
			)

	def test_a_kept_group_association_row_saves(self):
		"""The move patch leaves a Function's extra Group rows, and later saves keep them."""
		group = self.make_group("_Test Kept Group")
		function = make_function("_Test Kept Association")
		frappe.get_doc(
			{
				"doctype": "Function Association",
				"parenttype": "Function",
				"parentfield": "associations",
				"parent": function.name,
				"association_type": "Group",
				"association": group.name,
			}
		).db_insert()
		function.reload()

		function.description = "Still saves"
		function.save(ignore_permissions=True)

		self.assertEqual([row.association for row in function.associations], [group.name])


class TestFunctionMeetingLink(RollbackEachTest):
	def test_only_an_https_meeting_link_saves(self):
		function = make_function("_Test Online Meeting", meeting_url="https://meet.example.org/abc")
		self.assertEqual(function.meeting_url, "https://meet.example.org/abc")

		for unsafe in (
			"javascript:alert(1)",
			"http://x.org",
			"https://x.org/a\r\nATTENDEE:mailto:x@example.org",
			"https://x.org/a\nX:1",
			"https://x.org/a b",
			"https://x.org/a\tb",
		):
			function.meeting_url = unsafe
			with self.subTest(unsafe), self.assertRaises(frappe.ValidationError):
				function.save(ignore_permissions=True)

		with self.assertRaisesRegex(frappe.ValidationError, "Online Meeting Link must be an https link"):
			make_function("_Test Online Plain Link", meeting_url="http://x.org")

	def test_a_stored_link_is_not_checked_again_on_an_unrelated_save(self):
		function = make_function("_Test Online Old Link", meeting_url="https://meet.example.org/abc")
		frappe.db.set_value("Function", function.name, "meeting_url", "http://old.example.org")

		function.reload()
		function.description = "Now with notes"
		function.save(ignore_permissions=True)


class TestFunctionCalendar(RollbackEachTest):
	def get_events(self, *names):
		filters = json.dumps([["Function", "name", "in", names]])
		events = get_calendar_events("2031-05-01", "2031-05-08", filters)
		return {
			event.name: (event.function_name, event.start_date, event.end_date, event.all_day)
			for event in events
		}

	def test_entries_show_the_name_at_their_hours(self):
		timed = make_function("_Test Early Service", start_time="09:00:00", end_time="10:30:00")
		open_ended = make_function("_Test Prayer Hour", start_time="19:00:00")
		all_day = make_function("_Test Retreat Days", all_day=1, end_date="2031-05-03")
		untimed = make_function("_Test Clean-Up Day")

		self.assertEqual(
			self.get_events(timed.name, open_ended.name, all_day.name, untimed.name),
			{
				timed.name: ("_Test Early Service", "2031-05-01 09:00:00", "2031-05-01 10:30:00", 0),
				open_ended.name: ("_Test Prayer Hour", "2031-05-01 19:00:00", "2031-05-01 20:00:00", 0),
				all_day.name: ("_Test Retreat Days", date(2031, 5, 1), date(2031, 5, 3), 1),
				untimed.name: ("_Test Clean-Up Day", date(2031, 5, 1), date(2031, 5, 1), 1),
			},
		)

	def test_a_drag_moves_the_day_and_the_hours(self):
		timed = make_function("_Test Moved Service", start_time="09:00:00", end_time="10:30:00")
		move_on_calendar(
			json.dumps(
				{"name": timed.name, "start_date": "2031-05-02 11:00:00", "end_date": "2031-05-02 12:30:00"}
			)
		)
		timed.reload()
		self.assertEqual(
			(timed.start_date, timed.start_time, timed.end_date, timed.end_time),
			(date(2031, 5, 2), timedelta(hours=11), None, timedelta(hours=12, minutes=30)),
		)

	def test_a_drag_keeps_an_all_day_function_all_day(self):
		# The calendar sends the last second of a one-day entry, and the midnight after a longer one.
		retreat = make_function("_Test Moved Retreat", all_day=1)
		for end, end_date in (("2031-05-04 23:59:59", None), ("2031-05-06 00:00:00", date(2031, 5, 5))):
			move_on_calendar(
				json.dumps({"name": retreat.name, "start_date": "2031-05-04 00:00:00", "end_date": end})
			)
			retreat.reload()
			self.assertEqual(
				(retreat.all_day, retreat.start_date, retreat.end_date), (1, date(2031, 5, 4), end_date)
			)

	def test_a_drop_on_the_all_day_row_moves_only_the_day(self):
		# The calendar sends 24 hours from the time where the entry was let go.
		timed = make_function("_Test Dropped Service", start_time="09:00:00", end_time="10:30:00")
		move_on_calendar(
			json.dumps(
				{
					"name": timed.name,
					"all_day": 1,
					"start_date": "2031-05-03 09:30:00",
					"end_date": "2031-05-04 09:29:59",
				}
			)
		)
		timed.reload()
		self.assertEqual(
			(timed.all_day, timed.start_date, timed.start_time, timed.end_date, timed.end_time),
			(0, date(2031, 5, 3), timedelta(hours=9), None, timedelta(hours=10, minutes=30)),
		)

	def test_another_churchs_function_is_not_on_the_calendar(self):
		_root, church_a, church_b = make_two_churches()
		staff = ensure_user("_test_function_calendar@example.com", "Calendar Staff", roles=("Church Staff",))
		set_user_church(staff, church_b)
		mine = make_function("_Test Calendar Mine", church=church_b)
		theirs = make_function("_Test Calendar Theirs", church=church_a)

		frappe.set_user(staff)

		self.assertEqual(set(self.get_events(mine.name, theirs.name)), {mine.name})

	def test_a_drag_needs_write_access(self):
		function = make_function("_Test Unmovable Service", start_time="09:00:00")
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			move_on_calendar(
				json.dumps(
					{
						"name": function.name,
						"start_date": "2031-05-02 09:00:00",
						"end_date": "2031-05-02 10:00:00",
					}
				)
			)
