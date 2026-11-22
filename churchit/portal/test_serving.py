# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member app's serving and room endpoints."""

from unittest.mock import patch

import frappe
from frappe.utils import add_days, add_to_date, getdate, now_datetime

from churchit.church_foundations.church_access import set_user_church
from churchit.church_operations.doctype.room_booking.test_room_request import make_room
from churchit.church_website.pages import sync_page_switches
from churchit.portal import serving
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
	make_two_churches,
)


def ministry_name_of(name):
	return frappe.db.get_value("Ministry", name, "ministry_name")


PUBLISH = "churchit.portal.realtime.frappe.publish_realtime"


class TestServing(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.email = ensure_user("_test_portal_serving@example.com", "Serving")
		cls.member = make_person("_Test Portal Serving", "Member", church=cls.branch_a, user=cls.email)
		cls.other = make_person("_Test Portal Serving", "Other", church=cls.branch_a)
		ministry = ensure(
			"Ministry",
			{"ministry_name": "_Test Portal Ministry"},
			{"ministry_name": "_Test Portal Ministry", "church": cls.branch_a},
		)
		cls.position = make_team_position(
			"_Test Portal Greeter",
			[cls.member.name, cls.other.name],
			ministry_name=ministry_name_of(ministry),
			church=cls.branch_a,
		)
		function = make_function(
			"_Test Portal Serving Sunday", start_date=add_days(getdate(), 5), church=cls.branch_a
		)
		cls.mine = make_team_assignment(function.name, cls.position.name, cls.member.name)
		cls.theirs = make_team_assignment(function.name, cls.position.name, cls.other.name)
		cls.addClassCleanup(frappe.clear_cache)

	def setUp(self):
		super().setUp()
		set_user_church(self.email, self.branch_a)
		frappe.set_user(self.email)

	def tearDown(self):
		frappe.flags.in_web_form = False
		super().tearDown()

	def test_a_member_reads_only_their_own_assignment_with_what_they_may_answer(self):
		data = serving.get_serving()

		self.assertEqual([row["name"] for row in data["assignments"]], [self.mine.name])
		row = data["assignments"][0]
		self.assertTrue(
			row["needs_answer"] and row["can_accept"] and row["can_decline"] and row["can_pass_on"]
		)
		self.assertIn("_Test Portal Greeter", row["position"])

	def test_an_accepted_assignment_needs_no_answer(self):
		frappe.db.set_value("Ministry Team Assignment", self.mine.name, "status", "Accepted")

		row = serving.get_serving()["assignments"][0]

		self.assertFalse(row["needs_answer"] or row["can_accept"])
		self.assertTrue(row["can_decline"])

	def test_blocks_and_positions_are_the_members_own(self):
		frappe.get_doc(
			{
				"doctype": "Ministry Team Block",
				"person": self.member.name,
				"from_date": add_days(getdate(), 2),
				"to_date": add_days(getdate(), 3),
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Ministry Team Block",
				"person": self.other.name,
				"from_date": add_days(getdate(), 2),
				"to_date": add_days(getdate(), 3),
			}
		).insert(ignore_permissions=True)

		data = serving.get_serving()

		self.assertEqual(len(data["blocks"]), 1)
		self.assertEqual([row["position"] for row in data["positions"]], [self.position.name])

	def test_a_login_without_a_person_is_refused(self):
		stranger = ensure_user("_test_portal_serving_none@example.com", "Nobody")
		frappe.set_user(stranger)

		with self.assertRaises(frappe.PermissionError):
			serving.get_serving()

	def test_guests_are_refused(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			serving.get_serving()

	def test_a_switched_off_page_is_refused(self):
		self.switch_off("ministry-team")

		with self.assertRaises(frappe.PermissionError):
			serving.get_serving()

	def switch_off(self, route):
		frappe.set_user("Administrator")
		sync_page_switches()
		features = frappe.get_single("Church Features")
		features.get("website_pages", {"route": route})[0].enabled = 0
		features.save()
		frappe.clear_cache()
		frappe.set_user(self.email)

	def test_only_an_https_meeting_link_is_sent(self):
		function = frappe.db.get_value("Ministry Team Assignment", self.mine.name, "function")
		frappe.db.set_value("Function", function, "meeting_url", "javascript:alert(1)")

		self.assertIsNone(serving.get_serving()["assignments"][0]["meeting_url"])

		frappe.db.set_value("Function", function, "meeting_url", "https://example.com/meet")
		self.assertEqual(serving.get_serving()["assignments"][0]["meeting_url"], "https://example.com/meet")

	def test_a_function_is_read_once_for_several_assignments(self):
		second = make_team_position(
			"_Test Portal Usher",
			[self.member.name],
			ministry_name=ministry_name_of(self.position.ministry),
			church=self.branch_a,
		)
		function = frappe.db.get_value("Ministry Team Assignment", self.mine.name, "function")
		make_team_assignment(function, second.name, self.member.name)

		with patch.object(serving, "get_team_schedule", wraps=serving.get_team_schedule) as schedule:
			rows = serving.get_serving()["assignments"]

		self.assertEqual(len(rows), 2)
		self.assertEqual(schedule.call_count, 1)

	def test_another_churchs_member_sees_nothing_of_these_assignments(self):
		frappe.set_user("Administrator")
		email = ensure_user("_test_portal_serving_b@example.com", "ServingB")
		make_person("_Test Portal Serving", "Branch B", church=self.branch_b, user=email)
		set_user_church(email, self.branch_b)
		frappe.set_user(email)

		self.assertEqual(serving.get_serving()["assignments"], [])

	def test_a_declined_replacement_tells_the_person_who_asked(self):
		frappe.set_user("Administrator")
		function = frappe.db.get_value("Ministry Team Assignment", self.mine.name, "function")
		frappe.delete_doc("Ministry Team Assignment", self.theirs.name, force=True)
		request = frappe.get_doc(
			{
				"doctype": "Ministry Team Assignment",
				"function": function,
				"position": self.position.name,
				"person": self.other.name,
				"replaces": self.mine.name,
			}
		)
		request.flags.is_replacement_request = True
		request.insert(ignore_permissions=True)
		request.reload()
		request.status = "Declined"

		with patch(PUBLISH) as publish:
			request.save(ignore_permissions=True)

		publish.assert_any_call(
			"churchit_portal",
			{"topic": "serving", "name": self.mine.name},
			user=self.email,
			after_commit=True,
		)

	def test_a_deleted_assignment_tells_the_person(self):
		frappe.set_user("Administrator")

		with patch(PUBLISH) as publish:
			frappe.delete_doc("Ministry Team Assignment", self.mine.name, force=True)

		publish.assert_any_call(
			"churchit_portal",
			{"topic": "serving", "name": self.mine.name},
			user=self.email,
			after_commit=True,
		)

	def test_a_new_assignment_tells_the_person_once_committed(self):
		function = make_function(
			"_Test Portal Serving Later", start_date=add_days(getdate(), 6), church=self.branch_a
		)
		frappe.set_user("Administrator")

		with patch(PUBLISH) as publish:
			assignment = make_team_assignment(function.name, self.position.name, self.member.name)

		publish.assert_any_call(
			"churchit_portal",
			{"topic": "serving", "name": assignment.name},
			user=self.email,
			after_commit=True,
		)


class TestRooms(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.room_a = make_room("_Test Portal Hall A", cls.branch_a)
		cls.closed_a = make_room("_Test Portal Closed A", cls.branch_a, is_bookable=0)
		cls.room_b = make_room("_Test Portal Hall B", cls.branch_b)
		cls.email = ensure_user("_test_portal_rooms@example.com", "Rooms")
		cls.member = make_person("_Test Portal Rooms", "Member", church=cls.branch_a, user=cls.email).name
		cls.other_email = ensure_user("_test_portal_rooms_other@example.com", "RoomsOther")
		cls.other = make_person("_Test Portal Rooms", "Other", church=cls.branch_a, user=cls.other_email).name
		cls.email_b = ensure_user("_test_portal_rooms_b@example.com", "RoomsB")
		make_person("_Test Portal Rooms", "Branch B", church=cls.branch_b, user=cls.email_b)
		cls.addClassCleanup(frappe.clear_cache)

	def setUp(self):
		super().setUp()
		set_user_church(self.email, self.branch_a)
		set_user_church(self.other_email, self.branch_a)
		set_user_church(self.email_b, self.branch_b)
		frappe.set_user(self.email)

	def tearDown(self):
		frappe.flags.in_web_form = False
		frappe.set_user("Administrator")
		for name in frappe.get_all(
			"Room Booking", filters={"room": ("in", [self.room_a, self.room_b])}, pluck="name"
		):
			frappe.delete_doc("Room Booking", name, force=True, ignore_permissions=True)
		super().tearDown()

	def book(self, hour=9, room=None, **values):
		return serving.request_room(
			room or self.room_a,
			f"2036-04-04 {hour:02d}:00:00",
			f"2036-04-04 {hour + 1:02d}:00:00",
			values.pop("purpose", "_Test Portal meeting"),
			**values,
		)

	def test_only_the_members_bookable_rooms_are_offered(self):
		names = {room["name"] for room in serving.get_rooms()["rooms"]}

		self.assertIn(self.room_a, names)
		self.assertNotIn(self.closed_a, names)
		self.assertNotIn(self.room_b, names)

	def test_a_request_takes_the_members_own_person_and_lists_for_them_only(self):
		result = self.book()

		self.assertEqual(frappe.db.get_value("Room Booking", result["name"], "requester"), self.member)
		self.assertEqual([row["name"] for row in serving.get_room_requests()["items"]], [result["name"]])
		frappe.set_user(self.other_email)
		self.assertEqual(serving.get_room_requests()["items"], [])

	def test_a_request_for_a_room_of_another_church_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			self.book(room=self.room_b)

	def test_the_member_rules_hold_even_for_staff_with_a_person(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Person", self.member, "user", "Administrator")
		past = add_to_date(now_datetime(), hours=-3)

		with self.assertRaisesRegex(frappe.ValidationError, "has not passed yet"):
			serving.request_room(self.room_a, str(past), str(add_to_date(past, hours=1)), "_Test late")
		frappe.db.set_value("Person", self.member, "user", self.email)

	def test_another_members_request_cannot_be_read_or_changed(self):
		name = self.book()["name"]
		frappe.set_user(self.other_email)

		with self.assertRaises(frappe.PermissionError):
			serving.get_room_request(name)
		with self.assertRaises(frappe.PermissionError):
			serving.update_room_request(
				name, self.room_a, "2036-04-04 09:00:00", "2036-04-04 10:00:00", "_Test hijack"
			)

	def test_a_member_changes_their_own_request(self):
		name = self.book()["name"]

		result = serving.update_room_request(
			name,
			self.room_a,
			"2036-04-04 11:00:00",
			"2036-04-04 12:00:00",
			"_Test moved",
			notes="Bring chairs",
		)

		row = serving.get_room_request(name)
		self.assertEqual(
			(row["purpose"], row["notes"], row["start_time"]), ("_Test moved", "Bring chairs", "11:00:00")
		)
		self.assertTrue(row["can_edit"])
		self.assertEqual(result["name"], name)

	def test_a_cancelled_request_cannot_be_changed(self):
		name = self.book()["name"]
		frappe.db.set_value("Room Booking", name, "status", "Cancelled")

		with self.assertRaises(frappe.PermissionError):
			serving.update_room_request(
				name, self.room_a, "2036-04-04 11:00:00", "2036-04-04 12:00:00", "_Test again"
			)

	def test_a_switched_off_page_is_refused(self):
		name = self.book()["name"]
		frappe.set_user("Administrator")
		sync_page_switches()
		features = frappe.get_single("Church Features")
		features.get("website_pages", {"route": "room-request"})[0].enabled = 0
		features.save()
		frappe.clear_cache()
		frappe.set_user(self.email)

		for call in (serving.get_rooms, serving.get_room_requests, lambda: serving.get_room_request(name)):
			with self.assertRaises(frappe.PermissionError):
				call()
		with self.assertRaises(frappe.PermissionError):
			self.book()
		with self.assertRaises(frappe.PermissionError):
			serving.update_room_request(
				name, self.room_a, "2036-04-04 11:00:00", "2036-04-04 12:00:00", "_Test again"
			)

	def test_a_member_of_another_church_cannot_read_or_change_a_request(self):
		name = self.book()["name"]
		frappe.set_user(self.email_b)

		with self.assertRaises(frappe.PermissionError):
			serving.get_room_request(name)
		with self.assertRaises(frappe.PermissionError):
			serving.update_room_request(
				name, self.room_a, "2036-04-04 11:00:00", "2036-04-04 12:00:00", "_Test hijack"
			)
		self.assertEqual(serving.get_room_requests()["items"], [])

	def test_a_denied_request_cannot_be_changed(self):
		name = self.book()["name"]
		frappe.db.set_value("Room Booking", name, "status", "Denied")

		self.assertFalse(serving.get_room_request(name)["can_edit"])
		with self.assertRaises(frappe.PermissionError):
			serving.update_room_request(
				name, self.room_a, "2036-04-04 11:00:00", "2036-04-04 12:00:00", "_Test again"
			)

	def test_a_request_that_has_ended_cannot_be_changed(self):
		name = self.book()["name"]
		past = add_to_date(now_datetime(), days=-2)
		frappe.db.set_value(
			"Room Booking", name, {"start_datetime": past, "end_datetime": add_to_date(past, hours=1)}
		)

		self.assertFalse(serving.get_room_request(name)["can_edit"])
		with self.assertRaises(frappe.PermissionError):
			serving.update_room_request(
				name, self.room_a, "2036-04-04 11:00:00", "2036-04-04 12:00:00", "_Test again"
			)

	def test_coming_requests_come_first_soonest_first_then_past_ones(self):
		later = self.book(hour=12)["name"]
		sooner = self.book(hour=9)["name"]
		past_start = add_to_date(now_datetime(), days=-2)
		past = self.book(hour=15)["name"]
		frappe.db.set_value(
			"Room Booking",
			past,
			{"start_datetime": past_start, "end_datetime": add_to_date(past_start, hours=1)},
		)

		names = [row["name"] for row in serving.get_room_requests()["items"]]

		self.assertEqual(names, [sooner, later, past])

	def test_the_member_flag_is_restored_after_a_request(self):
		self.book()

		self.assertFalse(frappe.flags.in_web_form)

	def test_room_writes_are_rate_limited(self):
		for function in (serving.request_room, serving.update_room_request):
			self.assertTrue(hasattr(function, "__wrapped__"), function.__name__)

	def test_a_deleted_request_tells_the_requester(self):
		name = self.book()["name"]
		frappe.set_user("Administrator")

		with patch(PUBLISH) as publish:
			frappe.delete_doc("Room Booking", name, force=True)

		publish.assert_any_call(
			"churchit_portal", {"topic": "rooms", "name": name}, user=self.email, after_commit=True
		)

	def test_a_decision_tells_the_requester_once_committed(self):
		name = self.book()["name"]
		frappe.flags.in_web_form = False
		frappe.set_user("Administrator")

		with patch(PUBLISH) as publish:
			booking = frappe.get_doc("Room Booking", name)
			booking.status = "Approved"
			booking.save()

		publish.assert_any_call(
			"churchit_portal", {"topic": "rooms", "name": name}, user=self.email, after_commit=True
		)
