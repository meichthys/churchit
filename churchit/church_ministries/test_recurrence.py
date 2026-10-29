# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import calendar
from datetime import date, time, timedelta
from unittest.mock import patch

import frappe
from frappe.utils import add_days, get_datetime, getdate

from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries.doctype.function.function import _as_time
from churchit.church_ministries.recurrence import (
	create_missing_occurrences,
	create_scheduled_functions,
	get_occurrence_dates,
)
from churchit.church_ministries.report.recurring_functions import recurring_functions
from churchit.ics import get_public_calendar
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)
from churchit.tests.test_ics import request_feed, unfold
from churchit.www.calendar import get_events


def weekday_name(day: date) -> str:
	return calendar.day_name[day.weekday()]


def occurrences(template) -> list[frappe._dict]:
	return frappe.get_all(
		"Function",
		filters={"source_template": template.name},
		fields=["name", "start_date", "end_date", "start_time", "auto_repeat"],
		order_by="start_date asc",
	)


def occurrence_dates(template) -> list[date]:
	return [getdate(row.start_date) for row in occurrences(template)]


def rule(**values) -> frappe._dict:
	return frappe._dict(
		{
			"repeat_interval": 1,
			"repeat_monthly_by": "Day of Month",
			"repeat_day_of_week": None,
			"repeat_week_of_month": None,
			"repeat_month_day": None,
			"skip_dates": [],
			**values,
		}
	)


class TestOccurrenceDates(RollbackEachTest):
	def test_second_sunday_of_each_month(self):
		template = rule(
			start_date=date(2029, 12, 9),
			repeat_frequency="Monthly",
			repeat_monthly_by="Weekday",
			repeat_week_of_month="Second",
			repeat_day_of_week="Sunday",
		)
		self.assertEqual(
			get_occurrence_dates(template, date(2030, 1, 1), date(2030, 3, 31)),
			[date(2030, 1, 13), date(2030, 2, 10), date(2030, 3, 10)],
		)

	def test_last_friday_of_each_month(self):
		template = rule(
			start_date=date(2029, 12, 28),
			repeat_frequency="Monthly",
			repeat_monthly_by="Weekday",
			repeat_week_of_month="Last",
			repeat_day_of_week="Friday",
		)
		self.assertEqual(
			get_occurrence_dates(template, date(2030, 1, 1), date(2030, 2, 28)),
			[date(2030, 1, 25), date(2030, 2, 22)],
		)

	def test_day_31_falls_on_the_last_day_of_a_shorter_month(self):
		template = rule(start_date=date(2030, 1, 31), repeat_frequency="Monthly", repeat_month_day=31)
		self.assertEqual(
			get_occurrence_dates(template, date(2030, 2, 1), date(2030, 4, 30)),
			[date(2030, 2, 28), date(2030, 3, 31), date(2030, 4, 30)],
		)

	def test_a_skip_date_is_left_out(self):
		template = rule(
			start_date=date(2030, 3, 1),
			repeat_frequency="Daily",
			skip_dates=[frappe._dict(date="2030-03-03")],
		)
		self.assertEqual(
			get_occurrence_dates(template, date(2030, 3, 2), date(2030, 3, 4)),
			[date(2030, 3, 2), date(2030, 3, 4)],
		)


class TestRecurrence(RollbackEachTest):
	def make_template(self, name, **values):
		return make_function(name, **{"auto_repeat": 1, "repeat_horizon_weeks": 8, **values})

	def test_every_second_sunday_with_a_skip_date(self):
		today = getdate()
		start = today - timedelta(days=(today.weekday() + 1) % 7 + 14)
		expected = [start + timedelta(days=14 * step) for step in range(1, 7)]
		expected = [day for day in expected if today <= day <= today + timedelta(weeks=8)]
		skipped = expected.pop(1)
		template = self.make_template(
			"_Test Fortnightly",
			start_date=start,
			repeat_frequency="Weekly",
			repeat_interval=2,
			repeat_day_of_week="Sunday",
			skip_dates=[{"date": skipped, "reason": "Joint service"}],
		)

		create_scheduled_functions()

		self.assertEqual(occurrence_dates(template), expected)

	def test_a_second_run_creates_no_duplicate(self):
		template = self.make_template(
			"_Test Weekly Twice",
			start_date=add_days(getdate(), -3),
			repeat_frequency="Weekly",
			repeat_day_of_week=weekday_name(add_days(getdate(), 1)),
		)
		create_missing_occurrences(template, getdate())
		first = occurrence_dates(template)

		create_missing_occurrences(template, getdate())

		self.assertEqual(len(first), 8)
		self.assertEqual(occurrence_dates(template), first)

	def test_the_templates_own_date_is_not_copied(self):
		start = getdate()
		template = self.make_template(
			"_Test Starts Today",
			start_date=start,
			repeat_frequency="Weekly",
			repeat_day_of_week=weekday_name(start),
		)
		create_missing_occurrences(template, start)

		self.assertEqual(occurrence_dates(template)[0], add_days(start, 7))

	def test_a_deleted_occurrence_is_not_created_again(self):
		template = self.make_template(
			"_Test Deleted Week",
			start_date=add_days(getdate(), -7),
			repeat_frequency="Weekly",
			repeat_day_of_week=weekday_name(getdate()),
		)
		create_missing_occurrences(template, getdate())
		latest = occurrences(template)[-1]

		frappe.delete_doc("Function", latest.name)
		template = frappe.get_doc("Function", template.name)
		create_missing_occurrences(template, getdate())

		self.assertEqual([getdate(row.date) for row in template.skip_dates], [getdate(latest.start_date)])
		self.assertNotIn(getdate(latest.start_date), occurrence_dates(template))

	def test_a_published_template_shows_its_occurrences_on_the_calendar_and_in_the_feed(self):
		template = self.make_template(
			"_Test Published Weekly",
			start_date=getdate(),
			publish=1,
			repeat_frequency="Weekly",
			repeat_day_of_week=weekday_name(getdate()),
		)
		create_missing_occurrences(template, getdate())
		names = [row.name for row in occurrences(template)]

		events = {event["id"] for event in get_events(getdate(), add_days(getdate(), 60))}
		self.assertTrue(set(names) <= events)
		frappe.set_user("Guest")
		try:
			feed = unfold(request_feed(self, get_public_calendar, church=template.church))
		finally:
			frappe.set_user("Administrator")
		for name in names:
			self.assertIn(f"UID:{name}@", feed)

	def test_a_link_only_template_makes_link_only_occurrences_with_its_meeting_link(self):
		template = self.make_template(
			"_Test Link Only Weekly",
			start_date=getdate(),
			publish=1,
			is_link_only=1,
			meeting_url="https://example.com/meet",
			repeat_frequency="Weekly",
			repeat_day_of_week=weekday_name(getdate()),
		)
		create_missing_occurrences(template, getdate())
		rows = frappe.get_all(
			"Function",
			filters={"source_template": template.name},
			fields=["name", "is_link_only", "meeting_url"],
		)

		self.assertTrue(rows)
		self.assertEqual(
			{(row.is_link_only, row.meeting_url) for row in rows}, {(1, "https://example.com/meet")}
		)
		events = {event["id"] for event in get_events(getdate(), add_days(getdate(), 60))}
		self.assertFalse(events & {row.name for row in rows})
		frappe.set_user("Guest")
		try:
			feed = unfold(request_feed(self, get_public_calendar, church=template.church))
		finally:
			frappe.set_user("Administrator")
		for row in rows:
			self.assertNotIn(f"UID:{row.name}@", feed)

	def test_an_occurrence_of_a_deleted_template_can_be_deleted(self):
		template = self.make_template(
			"_Test Gone Template",
			start_date=add_days(getdate(), -7),
			repeat_frequency="Weekly",
			repeat_day_of_week=weekday_name(getdate()),
			repeat_horizon_weeks=2,
		)
		create_missing_occurrences(template, getdate())
		occurrence = occurrences(template)[0]

		frappe.delete_doc("Function", template.name, force=True)
		frappe.delete_doc("Function", occurrence.name)

		self.assertFalse(frappe.db.exists("Function", occurrence.name))

	def test_a_duplicated_occurrence_is_not_an_occurrence(self):
		template = self.make_template(
			"_Test Duplicated Week",
			start_date=add_days(getdate(), -7),
			repeat_frequency="Weekly",
			repeat_day_of_week=weekday_name(getdate()),
		)
		create_missing_occurrences(template, getdate())

		duplicate = frappe.copy_doc(
			frappe.get_doc("Function", occurrences(template)[0].name), ignore_no_copy=False
		)

		self.assertIsNone(duplicate.source_template)

	def test_a_user_cannot_set_a_source_template(self):
		template = self.make_template("_Test Linked Template", repeat_frequency="Weekly")
		function = frappe.get_doc(
			{
				"doctype": "Function",
				"function_name": "_Test Hand Linked",
				"type": template.type,
				"start_date": "2031-05-08",
				"source_template": template.name,
			}
		)

		self.assertRaises(frappe.PermissionError, function.insert)

	def test_occurrences_copy_the_template(self):
		template = self.make_template(
			"_Test Weekly",
			start_date=add_days(getdate(), -10),
			repeat_frequency="Weekly",
			repeat_day_of_week="Sunday",
			start_time="10:00:00",
			end_time="11:00:00",
			description="Sunday service",
		)
		create_scheduled_functions()

		rows = occurrences(template)
		self.assertGreaterEqual(len(rows), 8)
		for row in rows:
			self.assertGreaterEqual(getdate(row.start_date), getdate())
			self.assertEqual(getdate(row.start_date).weekday(), 6)
			self.assertEqual(_as_time(row.start_time), time(10, 0))
			self.assertFalse(row.auto_repeat)
		self.assertEqual(frappe.db.get_value("Function", rows[0].name, "description"), "Sunday service")

	def test_occurrences_move_the_schedule_to_their_date(self):
		start = add_days(getdate(), -10)
		template = self.make_template(
			"_Test Scheduled Plan", start_date=start, repeat_frequency="Daily", repeat_horizon_weeks=1
		)
		template.append("schedule", {"description": "Welcome", "start": f"{start} 10:00:00"})
		template.save(ignore_permissions=True)
		create_scheduled_functions()

		for row in occurrences(template):
			occurrence = frappe.get_doc("Function", row.name)
			self.assertEqual(occurrence.schedule[0].start, get_datetime(f"{occurrence.start_date} 10:00:00"))

	def test_occurrences_keep_a_multi_day_functions_length(self):
		start = add_days(getdate(), -10)
		template = self.make_template(
			"_Test Retreat",
			start_date=start,
			end_date=add_days(start, 2),
			repeat_frequency="Weekly",
			repeat_day_of_week="Friday",
		)
		create_scheduled_functions()

		for row in occurrences(template):
			self.assertEqual(getdate(row.end_date), getdate(add_days(row.start_date, 2)))

	def test_nothing_is_created_after_repeat_until(self):
		template = self.make_template(
			"_Test Expired",
			start_date=add_days(getdate(), -10),
			repeat_frequency="Daily",
			repeat_until=add_days(getdate(), -1),
		)
		create_scheduled_functions()
		self.assertEqual(occurrences(template), [])

	def test_a_function_that_does_not_repeat_is_left_alone(self):
		template = make_function("_Test Once", start_date=add_days(getdate(), -10), auto_repeat=0)
		create_scheduled_functions()
		self.assertEqual(occurrences(template), [])

	def test_a_failing_template_keeps_no_occurrence_and_logs_an_error(self):
		template = self.make_template(
			"_Test Failing Weekly",
			start_date=add_days(getdate(), -3),
			repeat_frequency="Weekly",
			repeat_day_of_week="Sunday",
		)
		with patch("churchit.church_ministries.recurrence.copy_room_bookings", side_effect=RuntimeError):
			create_scheduled_functions()

		self.assertEqual(occurrences(template), [])
		self.assertTrue(frappe.db.exists("Error Log", {"reference_name": template.name}))

	def test_the_recurring_functions_report_names_the_weekday_of_the_month(self):
		template = self.make_template(
			"_Test Second Sunday",
			repeat_frequency="Monthly",
			repeat_monthly_by="Weekday",
			repeat_week_of_month="Second",
			repeat_day_of_week="Sunday",
		)
		_columns, rows = recurring_functions.execute({})
		row = next(row for row in rows if row["name"] == template.name)
		self.assertEqual(row["repeat_schedule"], "Second Sunday")


class TestRecurringRoomBookings(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.gated_room = ensure(
			"Room",
			{"room_name": "_Test Recurrence Gated Room"},
			{"room_name": "_Test Recurrence Gated Room", "is_bookable": 1, "requires_approval": 1},
		)
		self.open_room = ensure(
			"Room",
			{"room_name": "_Test Recurrence Open Room"},
			{"room_name": "_Test Recurrence Open Room", "is_bookable": 1, "requires_approval": 0},
		)
		self.requester = make_person("_Test Recurrence Booker").name
		self.start = add_days(getdate(), -7)
		self.template = make_function(
			"_Test Booked Weekly",
			start_date=self.start,
			auto_repeat=1,
			repeat_frequency="Weekly",
			repeat_day_of_week=weekday_name(self.start),
			repeat_until=getdate(),
			repeat_horizon_weeks=8,
		)

	def book(self, room, day, function=None, status="Requested"):
		return frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"requester": self.requester,
				"purpose": "_Test recurrence",
				"start_datetime": f"{day} 10:00:00",
				"end_datetime": f"{day} 11:00:00",
				"function": function,
				"status": status,
			}
		).insert(ignore_permissions=True)

	def occurrence(self):
		return frappe.get_doc("Function", {"source_template": self.template.name})

	def bookings(self, function):
		return frappe.get_all(
			"Room Booking",
			filters={"function": function},
			fields=["room", "status", "start_datetime", "end_datetime"],
			order_by="room asc",
		)

	def test_bookings_are_copied_requested_on_a_gated_room_and_approved_on_an_open_room(self):
		self.book(self.gated_room, self.start, self.template.name)
		self.book(self.open_room, self.start, self.template.name)
		self.book(self.open_room, add_days(self.start, -1), self.template.name, status="Cancelled")

		create_missing_occurrences(self.template, getdate())

		today = getdate()
		self.assertEqual(
			{(row.room, row.status) for row in self.bookings(self.occurrence().name)},
			{(self.gated_room, "Requested"), (self.open_room, "Approved")},
		)
		for row in self.bookings(self.occurrence().name):
			self.assertEqual(row.start_datetime, get_datetime(f"{today} 10:00:00"))
			self.assertEqual(row.end_datetime, get_datetime(f"{today} 11:00:00"))

	def test_a_deleted_occurrence_takes_its_bookings_and_its_date_is_skipped(self):
		self.book(self.open_room, self.start, self.template.name)
		create_missing_occurrences(self.template, getdate())
		occurrence = self.occurrence()

		frappe.delete_doc("Function", occurrence.name)

		self.assertEqual(self.bookings(occurrence.name), [])
		self.assertEqual(len(self.bookings(self.template.name)), 1)
		self.template.reload()
		self.assertEqual([getdate(row.date) for row in self.template.skip_dates], [getdate()])

	def test_a_copy_that_clashes_is_a_conflict_assigned_to_each_approver(self):
		self.book(self.gated_room, self.start, self.template.name)
		self.book(self.gated_room, getdate(), status="Approved")
		approvers = [
			ensure_user(
				f"_test_recurrence_approver_{number}@example.com", "Approver", roles=("Church Staff",)
			)
			for number in (1, 2)
		]
		room = frappe.get_doc("Room", self.gated_room)
		room.set("approvers", [{"user": user} for user in approvers])
		room.save(ignore_permissions=True)

		create_missing_occurrences(self.template, getdate())

		booking = frappe.get_doc("Room Booking", {"function": self.occurrence().name})
		self.assertEqual(booking.status, "Conflict")
		todos = frappe.get_all(
			"ToDo",
			filters={"reference_type": "Room Booking", "reference_name": booking.name, "status": "Open"},
			pluck="allocated_to",
		)
		self.assertCountEqual(todos, approvers)

	def test_a_clash_with_a_blocked_time_keeps_the_function_and_leaves_one_comment(self):
		self.book(self.open_room, self.start, self.template.name)
		self.book(self.open_room, getdate(), status="Blocked")

		create_missing_occurrences(self.template, getdate())

		occurrence = self.occurrence()
		self.assertEqual(self.bookings(occurrence.name), [])
		comments = frappe.get_all(
			"Comment",
			filters={
				"reference_doctype": "Function",
				"reference_name": occurrence.name,
				"comment_type": "Comment",
			},
			pluck="content",
		)
		self.assertEqual(len(comments), 1)
		self.assertIn("_Test Recurrence Open Room", comments[0], "the room name, not its ROOM- ID")


class TestRecurringSharedRoomBookings(RollbackEachTest):
	def test_a_shared_rooms_booking_keeps_the_equipment_of_the_church_that_made_it(self):
		_root, branch_a, _branch_b = make_two_churches()
		self.addCleanup(frappe.clear_cache)
		staff = ensure_user(
			"_test_recurrence_staff_a@example.com", "Recurrence Staff", roles=("Church Staff",)
		)
		set_user_church(staff, branch_a)
		room = ensure(
			"Room",
			{"room_name": "_Test Recurrence Shared Room"},
			{
				"room_name": "_Test Recurrence Shared Room",
				"church": branch_a,
				"is_shared": 1,
				"is_bookable": 1,
			},
		)
		asset = ensure(
			"Church Asset",
			{"title": "_Test Recurrence Projector"},
			{"title": "_Test Recurrence Projector", "church": branch_a, "is_bookable": 1},
		)
		start = add_days(getdate(), -7)
		template = make_function(
			"_Test Shared Room Weekly",
			church=branch_a,
			start_date=start,
			auto_repeat=1,
			repeat_frequency="Weekly",
			repeat_day_of_week=weekday_name(start),
			repeat_until=getdate(),
			repeat_horizon_weeks=8,
		)
		requester = make_person("_Test Recurrence", "Sharer", church=branch_a).name
		frappe.set_user(staff)
		try:
			frappe.get_doc(
				{
					"doctype": "Room Booking",
					"room": room,
					"assets": [{"asset": asset}],
					"function": template.name,
					"requester": requester,
					"purpose": "_Test recurrence",
					"start_datetime": f"{start} 10:00:00",
					"end_datetime": f"{start} 11:00:00",
				}
			).insert()
		finally:
			frappe.set_user("Administrator")

		create_missing_occurrences(template, getdate())

		occurrence = frappe.get_doc("Function", {"source_template": template.name})
		booking = frappe.get_doc("Room Booking", {"function": occurrence.name})
		self.assertEqual([row.asset for row in booking.assets], [asset])
