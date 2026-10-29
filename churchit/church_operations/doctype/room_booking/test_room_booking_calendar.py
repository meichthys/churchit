# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.desk.calendar import get_events

from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import RollbackEachTest, assert_scoped, ensure, ensure_user, make_two_churches

# The field map of room_booking_calendar.js.
FIELD_MAP = frappe.as_json(
	{"start": "start_datetime", "end": "end_datetime", "id": "name", "title": "purpose"}
)


class TestRoomBookingCalendar(RollbackEachTest):
	"""The room diary in the desk reads with get_list, so it shows only the reader's churches."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.room_a, cls.room_b = (
			ensure("Room", {"room_name": name}, {"room_name": name, "church": church, "is_bookable": 1})
			for name, church in (("_Test A4 Diary A", cls.branch_a), ("_Test A4 Diary B", cls.branch_b))
		)
		cls.requester_a = ensure(
			"Person",
			{"first_name": "_Test A4 Diary A"},
			{"first_name": "_Test A4 Diary A", "church": cls.branch_a},
		)
		cls.requester_b = ensure(
			"Person",
			{"first_name": "_Test A4 Diary B"},
			{"first_name": "_Test A4 Diary B", "church": cls.branch_b},
		)
		cls.staff_b = ensure_user(
			"_test_room_diary_staff_b@example.com", "Diary Staff B", roles=("Church Staff",)
		)
		set_user_church(cls.staff_b, cls.branch_b)

	def setUp(self):
		super().setUp()
		self.booking_a = self.book(self.room_a, self.requester_a)
		self.booking_b = self.book(self.room_b, self.requester_b)

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in frappe.get_all(
			"Room Booking", filters={"room": ["in", [self.room_a, self.room_b]]}, pluck="name"
		):
			frappe.delete_doc("Room Booking", name, force=True, ignore_permissions=True)
		super().tearDown()

	def book(self, room, requester):
		return frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"requester": requester,
				"purpose": "_Test A4 diary",
				"start_datetime": "2037-05-05 09:00:00",
				"end_datetime": "2037-05-05 10:00:00",
			}
		).insert(ignore_permissions=True)

	def events(self, start, end):
		return {event.name for event in get_events("Room Booking", start, end, FIELD_MAP)}

	def test_an_approved_booking_is_on_its_dates(self):
		self.assertEqual(self.booking_b.status, "Approved")
		frappe.set_user(self.staff_b)
		self.assertIn(self.booking_b.name, self.events("2037-05-01", "2037-05-31"))
		self.assertNotIn(self.booking_b.name, self.events("2037-06-01", "2037-06-30"))

	def test_another_churchs_booking_of_an_unshared_room_is_hidden(self):
		frappe.set_user(self.staff_b)
		self.assertNotIn(self.booking_a.name, self.events("2037-05-01", "2037-05-31"))
		assert_scoped(self, "Room Booking", self.staff_b, self.booking_b.name, self.booking_a.name)
