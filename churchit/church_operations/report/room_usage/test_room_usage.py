# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.desk.query_report import run

from churchit.church_foundations.church_access import set_user_church
from churchit.church_operations.report.room_usage.room_usage import execute
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches


def make_room(room_name, church, **values):
	return (
		frappe.get_doc(
			{"doctype": "Room", "room_name": room_name, "is_bookable": 1, "church": church, **values}
		)
		.insert(ignore_permissions=True)
		.name
	)


def make_asset(title, church):
	return (
		frappe.get_doc({"doctype": "Church Asset", "title": title, "is_bookable": 1, "church": church})
		.insert(ignore_permissions=True)
		.name
	)


def make_booking(room, requester, start, end, **values):
	return (
		frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"requester": requester,
				"purpose": "_Test usage",
				"start_datetime": start,
				"end_datetime": end,
				**values,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


class TestRoomUsage(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.manager_a = ensure_user("_test_usage_manager_a@example.com", "Usage A", roles=("Church Manager",))
		set_user_church(cls.manager_a, cls.branch_a)
		cls.staff_b = ensure_user("_test_usage_staff_b@example.com", "Usage B", roles=("Church Staff",))
		set_user_church(cls.staff_b, cls.branch_b)

		cls.requester_a = make_person("_Test Usage", "Requester A", church=cls.branch_a).name
		requester_b = make_person("_Test Usage", "Requester B", church=cls.branch_b).name
		cls.hall_a = make_room("_Test Usage Hall A", cls.branch_a)
		cls.shared_hall = make_room("_Test Usage Shared Hall", cls.branch_a, is_shared=1)
		cls.hall_b = make_room("_Test Usage Hall B", cls.branch_b)
		cls.rooms = (cls.hall_a, cls.shared_hall, cls.hall_b)
		cls.addClassCleanup(cls.delete_bookings)
		assets = [
			{"asset": make_asset(title, cls.branch_a)}
			for title in ("_Test Usage Projector", "_Test Usage Speaker")
		]

		cls.booking_a = make_booking(
			cls.hall_a, cls.requester_a, "2036-03-02 09:00:00", "2036-03-02 11:30:00", assets=assets
		)
		cls.shared_booking = make_booking(
			cls.shared_hall, cls.requester_a, "2036-03-03 18:00:00", "2036-03-03 20:00:00"
		)
		cls.booking_b = make_booking(cls.hall_b, requester_b, "2036-03-04 10:00:00", "2036-03-04 11:00:00")
		cls.overnight_booking = make_booking(
			cls.hall_b, requester_b, "2036-02-29 20:00:00", "2036-03-01 08:00:00", status="Cancelled"
		)
		cls.later_booking = make_booking(
			cls.hall_a, cls.requester_a, "2036-04-10 09:00:00", "2036-04-10 10:00:00"
		)

	@classmethod
	def delete_bookings(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Room Booking", filters={"room": ["in", cls.rooms]}, pluck="name"):
			frappe.delete_doc("Room Booking", name, force=True, ignore_permissions=True)

	def rows(self, **filters):
		_columns, data = execute({"from_date": "2036-03-01", "to_date": "2036-03-31", **filters})
		return {row.booking: row for row in data if row.room in self.rooms}

	def test_one_row_per_booking_with_its_room_equipment_and_hours(self):
		row = self.rows()[self.booking_a]

		self.assertEqual(
			(row.room, sorted(row.assets.split(", ")), row.hours, row.status, row.requester, row.purpose),
			(
				self.hall_a,
				["_Test Usage Projector", "_Test Usage Speaker"],
				2.5,
				"Approved",
				self.requester_a,
				"_Test usage",
			),
		)
		self.assertEqual(row._room_link_title, "_Test Usage Hall A")
		self.assertEqual(str(row.start_datetime), "2036-03-02 09:00:00")

	def test_the_dates_list_each_booking_that_overlaps_them(self):
		self.assertEqual(
			set(self.rows()),
			{self.booking_a, self.shared_booking, self.booking_b, self.overnight_booking},
		)

	def test_the_room_and_status_filters(self):
		self.assertEqual(set(self.rows(room=self.hall_a)), {self.booking_a})
		self.assertEqual(set(self.rows(status="Cancelled")), {self.overnight_booking})

	def test_a_church_sees_its_own_bookings_and_the_shared_room_diary(self):
		for user, own_booking, other_booking in (
			(self.manager_a, self.booking_a, self.booking_b),
			(self.staff_b, self.booking_b, self.booking_a),
		):
			frappe.set_user(user)
			listed = self.rows()
			self.assertIn(own_booking, listed)
			self.assertIn(self.shared_booking, listed)
			self.assertNotIn(other_booking, listed)

	def test_church_staff_run_the_report_but_cannot_filter_by_another_churchs_room(self):
		frappe.set_user(self.staff_b)
		result = run("Room Usage", {"from_date": "2036-03-01", "to_date": "2036-03-31"})
		self.assertIn(self.booking_b, [row["booking"] for row in result["result"]])

		with self.assertRaises(frappe.PermissionError):
			self.rows(room=self.hall_a)
