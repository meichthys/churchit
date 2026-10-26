# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import threading
from unittest.mock import patch

import frappe
from frappe.client import insert as insert_doc
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.church_access import set_user_church
from churchit.church_operations.doctype.room_booking.room_booking import (
	DECIDED_NOTIFICATION,
	create_decided_notification,
)
from churchit.patches.v1_0 import add_room_booking_decided_notification, remove_room_booking_pending_approval
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestRoomBooking(FrappeTestCase):
	def setUp(self):
		self.gated_room = _ensure(
			"Room",
			{"room_name": "_Test Gated Room"},
			{"room_name": "_Test Gated Room", "is_bookable": 1, "requires_approval": 1},
		)
		self.open_room = _ensure(
			"Room",
			{"room_name": "_Test Open Room"},
			{"room_name": "_Test Open Room", "is_bookable": 1, "requires_approval": 0},
		)
		self.requester = _ensure("Person", {"first_name": "_Test Booker"}, {"first_name": "_Test Booker"})

	def tearDown(self):
		# Bookings outlive the per-test rollback, so clear them here or the conflict
		# check trips on slots left behind by earlier tests in the same run.
		frappe.set_user("Administrator")
		for name in frappe.get_all(
			"Room Booking", filters={"room": ["in", [self.gated_room, self.open_room]]}, pluck="name"
		):
			frappe.delete_doc("Room Booking", name, force=True, ignore_permissions=True)

	def _make_booking(self, room, hour=9, **values):
		return frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"requester": self.requester,
				"purpose": "Test booking",
				"start_datetime": f"2031-03-04 {hour:02d}:00:00",
				"end_datetime": f"2031-03-04 {hour + 1:02d}:00:00",
				**values,
			}
		).insert(ignore_permissions=True)

	def _church_user(self):
		email = "_test_church_user@example.com"
		if not frappe.db.exists("User", email):
			user = frappe.new_doc("User")
			user.update({"email": email, "first_name": "_Test Church User"})
			user.flags.no_welcome_mail = True
			user.append("roles", {"role": "Church User"})
			user.insert(ignore_permissions=True)
		# A member books for their own Person.
		_ensure("Person", {"user": email}, {"first_name": "_Test Church User", "user": email})
		return email

	def test_booking_on_open_room_is_approved_immediately(self):
		self.assertEqual(self._make_booking(self.open_room).status, "Approved")

	def test_booking_on_gated_room_waits_for_approval(self):
		self.assertEqual(self._make_booking(self.gated_room).status, "Requested")

	def test_explicit_status_survives_auto_approval(self):
		booking = self._make_booking(self.open_room, status="Cancelled")
		self.assertEqual(booking.status, "Cancelled")

	def test_requester_cannot_approve_own_gated_booking(self):
		frappe.set_user(self._church_user())
		booking = self._make_booking(self.gated_room)
		self.assertEqual(booking.status, "Requested")
		booking.status = "Approved"
		with self.assertRaises(ValidationError):
			booking.save()

	def test_manager_can_approve_gated_booking(self):
		booking = self._make_booking(self.gated_room)
		booking.status = "Approved"
		booking.save()
		self.assertEqual(booking.status, "Approved")

	def test_approved_booking_can_still_be_edited(self):
		booking = self._make_booking(self.gated_room)
		booking.status = "Approved"
		booking.save()
		booking.notes = "Edited after approval"
		booking.save()  # should not raise
		self.assertEqual(booking.status, "Approved")

	def _approved_booking(self, room, owner):
		frappe.set_user(owner)
		booking = self._make_booking(room)
		frappe.set_user("Administrator")
		booking.status = "Approved"
		booking.save()
		return booking

	def _move(self, booking, user, **values):
		frappe.set_user(user)
		booking = frappe.get_doc("Room Booking", booking.name)
		booking.update(values)
		booking.save()
		return booking.status

	def test_moving_an_approved_booking_on_a_gated_room_returns_it_to_requested(self):
		user = self._church_user()
		later = {"start_datetime": "2031-03-04 13:00:00", "end_datetime": "2031-03-04 14:00:00"}
		self.assertEqual(
			self._move(self._approved_booking(self.gated_room, user), user, **later), "Requested"
		)

		manager = ensure_user("_test_booking_manager@example.com", "Manager", roles=("Church Manager",))
		booking = self._approved_booking(self.gated_room, user)
		self.assertEqual(
			self._move(
				booking, manager, start_datetime="2031-03-04 11:00:00", end_datetime="2031-03-04 12:00:00"
			),
			"Approved",
		)
		self.assertEqual(self._move(booking, user, notes="Bring chairs"), "Approved")

		frappe.set_user(user)
		booking = self._make_booking(self.open_room, hour=15)
		self.assertEqual(self._move(booking, user, **later), "Approved")

	def test_a_room_that_is_not_bookable_is_refused(self):
		closed_room = _ensure(
			"Room",
			{"room_name": "_Test Closed Room"},
			{"room_name": "_Test Closed Room", "is_bookable": 0},
		)
		frappe.db.set_value("Room", closed_room, "is_bookable", 0)
		with self.assertRaises(ValidationError):
			self._make_booking(closed_room)

		frappe.db.set_value("Room", closed_room, "is_bookable", 1)
		booking = self._make_booking(closed_room)
		self.addCleanup(frappe.delete_doc, "Room Booking", booking.name, force=True, ignore_permissions=True)
		frappe.db.set_value("Room", closed_room, "is_bookable", 0)
		booking.notes = "Bring chairs"
		booking.save()
		booking.start_datetime = "2031-03-04 08:00:00"
		with self.assertRaises(ValidationError):
			booking.save()

	def test_a_booking_without_a_room_asks_for_the_room(self):
		booking = frappe.get_doc(
			{
				"doctype": "Room Booking",
				"start_datetime": "2031-03-04 10:00:00",
				"end_datetime": "2031-03-04 11:00:00",
			}
		)
		with self.assertRaises(frappe.MandatoryError):
			booking.insert()

	def test_overlapping_booking_is_rejected(self):
		self._make_booking(self.open_room, hour=9)
		with self.assertRaises(ValidationError):
			self._make_booking(self.open_room, hour=9)

	def test_end_before_start_is_rejected(self):
		with self.assertRaises(ValidationError):
			self._make_booking(
				self.open_room, start_datetime="2031-03-04 12:00:00", end_datetime="2031-03-04 11:00:00"
			)

	def test_times_sent_as_text_are_compared_as_times(self):
		"""REST sends text, and "9:30" sorts after "10:30" as text."""

		def insert(start, end):
			return insert_doc(
				{
					"doctype": "Room Booking",
					"room": self.open_room,
					"requester": self.requester,
					"purpose": "_Test text times",
					"start_datetime": start,
					"end_datetime": end,
				}
			)

		with self.assertRaisesRegex(ValidationError, "End time must be after start time"):
			insert("2031-03-04 10:30:00", "2031-03-04 9:30:00")

		insert("2031-03-04 9:00:00", "2031-03-04 10:00:00")
		with self.assertRaisesRegex(ValidationError, "already booked"):
			insert("2031-03-04 9:30:00", "2031-03-04 10:30:00")


class TestRoomBookingAcrossChurches(RollbackEachTest):
	"""Only a room's own church books it, and every church books a shared room."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.staff_b = ensure_user("_test_booking_staff_b@example.com", "Staff B", roles=("Church Staff",))
		set_user_church(cls.staff_b, cls.branch_b)
		cls.requester_b = make_person("_Test Booking", "Requester B", church=cls.branch_b).name
		cls.requester_a = make_person("_Test Booking", "Requester A", church=cls.branch_a).name
		cls.room_a, cls.shared_room = (
			frappe.get_doc(
				{"doctype": "Room", "room_name": name, "is_bookable": 1, "church": cls.branch_a, **values}
			)
			.insert(ignore_permissions=True)
			.name
			for name, values in (("_Test Branch A Hall", {}), ("_Test Shared Hall B", {"is_shared": 1}))
		)

	def book(self, room, requester=None):
		return frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"requester": requester or self.requester_b,
				"purpose": "_Test across churches",
				"start_datetime": "2034-02-02 09:00:00",
				"end_datetime": "2034-02-02 10:00:00",
				"church": self.branch_b,
			}
		)

	def test_another_church_cannot_book_a_churchs_room(self):
		"""Frappe checks the create right on the church the caller sends, before it fetches the room's."""
		frappe.set_user(self.staff_b)
		with self.assertRaises(frappe.PermissionError):
			self.book(self.room_a).insert()

	def test_every_church_books_a_shared_room(self):
		frappe.set_user(self.staff_b)
		self.assertEqual(self.book(self.shared_room).insert().church, "")

	def test_a_requester_from_another_church_is_refused(self):
		frappe.set_user(self.staff_b)
		with self.assertRaises(frappe.PermissionError):
			self.book(self.shared_room, requester=self.requester_a).insert()

	def test_a_function_of_another_church_is_refused(self):
		room_b = frappe.get_doc(
			{"doctype": "Room", "room_name": "_Test Branch B Hall", "is_bookable": 1, "church": self.branch_b}
		).insert(ignore_permissions=True)
		function_a = make_function("_Test Function of A", church=self.branch_a).name

		frappe.set_user(self.staff_b)
		booking = self.book(room_b.name)
		booking.function = function_a
		with self.assertRaises(frappe.PermissionError):
			booking.insert()

	def test_a_shared_function_or_a_shared_room_serves_any_church(self):
		room_b = frappe.get_doc(
			{"doctype": "Room", "room_name": "_Test Branch B Room", "is_bookable": 1, "church": self.branch_b}
		).insert(ignore_permissions=True)
		shared_function = make_function(
			"_Test Shared Function", is_shared=1, shared_by_church=self.branch_a
		).name
		function_a = make_function("_Test Function of A Too", church=self.branch_a).name

		frappe.set_user(self.staff_b)
		for room, function in ((room_b.name, shared_function), (self.shared_room, function_a)):
			booking = self.book(room)
			booking.function = function
			self.assertEqual(booking.insert().function, function)
			booking.delete()

	def test_a_clash_names_no_booking_of_another_church(self):
		theirs = self.book(self.shared_room, requester=self.requester_a).insert(ignore_permissions=True)
		theirs.db_set("church", self.branch_a)

		frappe.set_user(self.staff_b)
		with self.assertRaises(frappe.ValidationError) as clash:
			self.book(self.shared_room).insert()
		self.assertNotIn(theirs.name, str(clash.exception))
		self.assertIn("1 booking(s) of another church", str(clash.exception))


class RoomBookingDecisionCase(RollbackEachTest):
	"""Rooms of church A with listed approvers, with Church Managers as approvers, and with none needed."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		users = {
			"approver_1": ("Church Staff", cls.branch_a),
			"approver_2": ("Church Staff", cls.branch_a),
			"staff_a": ("Church Staff", cls.branch_a),
			"manager_a": ("Church Manager", cls.branch_a),
			"manager_b": ("Church Manager", cls.branch_b),
		}
		for key, (role, church) in users.items():
			user = ensure_user(f"_test_booking_{key}@example.com", key, roles=(role,))
			set_user_church(user, church)
			setattr(cls, key, user)
		cls.requester = make_person("_Test Decision", "Requester", church=cls.branch_a).name
		cls.listed_room, cls.managed_room, cls.open_room = (
			frappe.get_doc(
				{"doctype": "Room", "room_name": name, "is_bookable": 1, "church": cls.branch_a, **values}
			)
			.insert(ignore_permissions=True)
			.name
			for name, values in (
				(
					"_Test A1 Listed Room",
					{
						"requires_approval": 1,
						"approvers": [{"user": cls.approver_1}, {"user": cls.approver_2}],
					},
				),
				("_Test A1 Managed Room", {"requires_approval": 1}),
				("_Test A1 Open Room", {}),
			)
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def book(self, room, hour=9, user=None, as_user=False, **values):
		"""A booking of *room* from *hour* for an hour, inserted with ignore_permissions unless *as_user*."""
		if user:
			frappe.set_user(user)
		booking = frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"requester": self.requester,
				"purpose": "_Test decision",
				"start_datetime": f"2032-05-06 {hour:02d}:00:00",
				"end_datetime": f"2032-05-06 {hour + 1:02d}:00:00",
				**values,
			}
		).insert(ignore_permissions=not as_user)
		frappe.set_user("Administrator")
		return booking

	def as_user(self, user, booking, method, *args):
		"""Run a decision method of *booking* as *user*, on a fresh copy, and return the stored status."""
		frappe.set_user(user)
		try:
			getattr(frappe.get_doc("Room Booking", booking.name), method)(*args)
		finally:
			frappe.set_user("Administrator")
		return frappe.db.get_value("Room Booking", booking.name, "status")

	def save_as(self, user, booking, **values):
		"""Save *values* on a fresh copy of *booking* as *user*, with the user's own permissions."""
		frappe.set_user(user)
		try:
			frappe.get_doc("Room Booking", booking.name).update(values).save()
		finally:
			frappe.set_user("Administrator")

	def open_todos(self, booking):
		return frappe.get_all(
			"ToDo",
			filters={"reference_type": "Room Booking", "reference_name": booking.name, "status": "Open"},
			pluck="allocated_to",
		)


class TestRoomBookingApprovers(RoomBookingDecisionCase):
	def test_a_listed_approver_decides_and_an_unlisted_staff_user_cannot(self):
		booking = self.book(self.listed_room)
		with self.assertRaises(frappe.PermissionError):
			self.as_user(self.staff_a, booking, "approve")
		self.assertEqual(self.as_user(self.approver_2, booking, "approve"), "Approved")
		with self.assertRaises(ValidationError):
			self.as_user(self.approver_1, booking, "deny")

		self.assertEqual(self.as_user(self.approver_1, self.book(self.listed_room, 11), "deny"), "Denied")

	def test_only_an_approver_denies_by_a_save_or_reopens_a_denied_booking(self):
		booking = self.book(self.listed_room, user=self.staff_a, as_user=True)
		with self.assertRaisesRegex(ValidationError, "deny"):
			self.save_as(self.manager_a, booking, status="Denied")
		self.assertEqual(self.as_user(self.approver_1, booking, "deny"), "Denied")

		with self.assertRaisesRegex(ValidationError, "reopen"):
			self.save_as(self.staff_a, booking, status="Requested")
		self.save_as(self.staff_a, booking, status="Cancelled")
		self.assertEqual(frappe.db.get_value("Room Booking", booking.name, "status"), "Cancelled")

	def test_another_churchs_manager_cannot_decide(self):
		booking = self.book(self.managed_room)
		with self.assertRaises(frappe.PermissionError):
			self.as_user(self.manager_b, booking, "approve")
		self.assertEqual(self.as_user(self.manager_a, booking, "approve"), "Approved")

	def test_an_approvers_own_booking_is_approved_at_once(self):
		self.assertEqual(self.book(self.listed_room, user=self.approver_1, as_user=True).status, "Approved")
		self.assertEqual(self.book(self.listed_room, 11, user=self.approver_1).status, "Requested")
		self.assertEqual(self.book(self.listed_room, 13, user=self.staff_a, as_user=True).status, "Requested")

	def test_a_move_by_an_approver_keeps_the_approval(self):
		later = {"start_datetime": "2032-05-06 15:00:00", "end_datetime": "2032-05-06 16:00:00"}
		own = self.book(self.listed_room, user=self.approver_1, as_user=True)
		frappe.set_user(self.approver_1)
		own.update(later)
		own.save()
		self.assertEqual(own.status, "Approved")

		theirs = self.book(self.listed_room, 11, user=self.staff_a, as_user=True)
		self.as_user(self.approver_1, theirs, "approve")
		frappe.set_user(self.staff_a)
		theirs.reload()
		theirs.update({"start_datetime": "2032-05-06 17:00:00", "end_datetime": "2032-05-06 18:00:00"})
		theirs.save()
		self.assertEqual(theirs.status, "Requested")

	def test_a_request_assigns_each_approver_and_a_decision_closes_the_assignments(self):
		booking = self.book(self.listed_room)
		self.assertCountEqual(self.open_todos(booking), [self.approver_1, self.approver_2])

		booking.reload()
		booking.notes = "_Test edited"
		booking.save()
		self.assertEqual(len(self.open_todos(booking)), 2)

		self.as_user(self.approver_1, booking, "approve")
		self.assertEqual(self.open_todos(booking), [])

	def test_a_room_without_a_list_assigns_the_managers_of_its_church(self):
		todos = self.open_todos(self.book(self.managed_room))
		self.assertIn(self.manager_a, todos)
		self.assertNotIn(self.manager_b, todos)

	def test_a_waiting_booking_moved_to_another_room_goes_to_that_rooms_approvers(self):
		booking = self.book(self.listed_room)
		booking.reload()
		booking.room = self.managed_room
		booking.save()
		self.assertEqual(booking.status, "Requested")
		todos = self.open_todos(booking)
		self.assertIn(self.manager_a, todos)
		self.assertNotIn(self.approver_1, todos)
		self.assertNotIn(self.approver_2, todos)

	def test_a_listed_approver_who_loses_the_staff_role_stops_approving(self):
		demoted = ensure_user("_test_booking_demoted@example.com", "demoted", roles=("Church Staff",))
		set_user_church(demoted, self.branch_a)
		frappe.get_doc("User", demoted).add_roles("Church Staff")
		room = frappe.get_doc(
			{
				"doctype": "Room",
				"room_name": "_Test A1 Demoted Room",
				"is_bookable": 1,
				"church": self.branch_a,
				"requires_approval": 1,
				"approvers": [{"user": demoted}, {"user": self.approver_1}],
			}
		).insert(ignore_permissions=True)
		user = frappe.get_doc("User", demoted)
		user.remove_roles("Church Staff")
		user.add_roles("Church User")
		self.addCleanup(frappe.clear_cache, user=demoted)
		# Without a staff role the user is a member, who books only as their own Person.
		person = make_person("_Test Decision", "Demoted", church=self.branch_a)
		frappe.db.set_value("Person", person.name, "user", demoted)

		own = self.book(room.name, user=demoted, as_user=True)
		self.assertEqual(own.status, "Requested")
		self.assertEqual(self.open_todos(own), [self.approver_1])
		with self.assertRaises(frappe.PermissionError):
			self.book(room.name, 11, user=demoted, as_user=True, status="Blocked", requester=None)

	def test_the_form_shows_the_decision_buttons_to_an_approver_without_a_to_do(self):
		booking = self.book(self.managed_room)
		for user, is_approver in ((self.manager_a, True), (self.staff_a, False), (self.manager_b, False)):
			frappe.set_user(user)
			booking.run_method("onload")
			self.assertEqual(booking.get_onload().is_approver, is_approver, user)

	def test_an_approver_cannot_read_another_churchs_booking(self):
		room_b = frappe.get_doc(
			{"doctype": "Room", "room_name": "_Test A1 Room B", "is_bookable": 1, "church": self.branch_b}
		).insert(ignore_permissions=True)
		requester_b = make_person("_Test Decision", "Requester B", church=self.branch_b).name
		theirs = self.book(room_b.name, requester=requester_b)
		assert_scoped(self, "Room Booking", self.approver_1, self.book(self.listed_room).name, theirs.name)

	def test_the_owner_hears_of_the_decision(self):
		create_decided_notification()
		booking = self.book(self.listed_room, user=self.staff_a, as_user=True)
		with patch("frappe.sendmail") as sendmail:
			self.as_user(self.approver_1, booking, "approve")
		decided = [call.kwargs for call in sendmail.call_args_list if "approved" in call.kwargs["subject"]]
		self.assertEqual([email["recipients"] for email in decided], [[self.staff_a]])

	def test_the_patches_replace_the_pending_approval_notification(self):
		if not frappe.db.exists("Notification", "Room Booking Pending Approval"):
			frappe.get_doc(
				{
					"doctype": "Notification",
					"name": "Room Booking Pending Approval",
					"subject": "Room booking pending approval",
					"document_type": "Room Booking",
					"event": "New",
					"enabled": 0,
					"message": "Pending",
				}
			).insert(ignore_permissions=True)
		frappe.delete_doc_if_exists("Notification", DECIDED_NOTIFICATION)

		with patch.dict(frappe.flags, {"in_patch": True}):
			for _run in range(2):
				remove_room_booking_pending_approval.execute()
				add_room_booking_decided_notification.execute()

		self.assertFalse(frappe.db.exists("Notification", "Room Booking Pending Approval"))
		notification = frappe.get_doc("Notification", DECIDED_NOTIFICATION)
		self.assertEqual((notification.is_standard, notification.enabled), (0, 1))
		self.assertEqual((notification.event, notification.value_changed), ("Value Change", "status"))


class TestBlockedRoomTime(RoomBookingDecisionCase):
	def block(self, user, hour=9, **values):
		return self.book(
			self.listed_room, hour, user=user, as_user=True, status="Blocked", requester=None, **values
		)

	def test_only_an_approver_of_the_room_blocks_a_time(self):
		with self.assertRaises(frappe.PermissionError):
			self.block(self.staff_a)
		blocked = self.block(self.approver_1)
		self.assertEqual((blocked.status, blocked.requester), ("Blocked", None))

	def test_a_request_needs_a_requester_and_a_blocked_time_does_not(self):
		with self.assertRaises(frappe.MandatoryError):
			self.book(self.open_room, requester=None)
		self.assertIsNone(self.block(self.approver_1).requester)

	def test_only_an_approver_of_the_room_removes_a_blocked_time(self):
		blocked = self.block(self.approver_1)
		frappe.set_user(self.manager_a)
		try:
			with self.assertRaisesRegex(frappe.PermissionError, "blocked time"):
				frappe.delete_doc("Room Booking", blocked.name)
		finally:
			frappe.set_user("Administrator")

		frappe.set_user(self.approver_1)
		try:
			frappe.delete_doc("Room Booking", blocked.name)
		finally:
			frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Room Booking", blocked.name))

	def test_a_blocked_time_needs_a_room(self):
		booking = frappe.get_doc({"doctype": "Room Booking", "status": "Blocked"})
		with self.assertRaisesRegex(ValidationError, "room to block"):
			booking.validate_blocked()

	def test_a_request_over_a_blocked_time_is_refused_even_when_asked_anyway(self):
		self.block(self.approver_1)
		for values in ({}, {"request_anyway": 1}, {"can_share_room": 1}):
			with self.assertRaisesRegex(ValidationError, "already booked"):
				self.book(self.listed_room, **values)

	def test_a_blocked_time_denies_the_requests_it_overlaps(self):
		requested = self.book(self.listed_room)
		conflict = self.book(self.listed_room, request_anyway=1)
		self.assertEqual(conflict.status, "Conflict")
		elsewhere = self.book(self.listed_room, 11)

		self.block(self.approver_1)

		for booking, status in ((requested, "Denied"), (conflict, "Denied"), (elsewhere, "Requested")):
			self.assertEqual(frappe.db.get_value("Room Booking", booking.name, "status"), status)
		self.assertEqual(self.open_todos(requested), [])
		self.assertEqual(self.open_todos(conflict), [])

	def test_an_approved_booking_refuses_the_blocked_time(self):
		self.book(self.listed_room, user=self.approver_1, as_user=True)
		with self.assertRaisesRegex(ValidationError, "already booked"):
			self.block(self.approver_1)


class TestRoomBookingConflicts(RoomBookingDecisionCase):
	def test_a_clash_asked_anyway_is_a_conflict_assigned_to_the_approvers(self):
		self.book(self.open_room, user=self.staff_a, as_user=True)
		with self.assertRaisesRegex(ValidationError, "already booked"):
			self.book(self.open_room)

		conflict = self.book(self.open_room, request_anyway=1)
		self.assertEqual(conflict.status, "Conflict")
		self.assertIn(self.manager_a, self.open_todos(conflict))

	def test_a_conflict_holds_no_time(self):
		self.book(self.open_room, 9)
		self.book(self.open_room, 10, request_anyway=1, start_datetime="2032-05-06 09:30:00")
		self.assertEqual(self.book(self.open_room, 10).status, "Approved")

	def test_bookings_that_both_can_share_the_room_do_not_clash(self):
		self.book(self.open_room, can_share_room=1)
		self.assertEqual(self.book(self.open_room, can_share_room=1).status, "Approved")
		with self.assertRaisesRegex(ValidationError, "already booked"):
			self.book(self.open_room)

	def test_keep_approves_this_booking_and_denies_the_requests_it_clashes_with(self):
		requested = self.book(self.listed_room)
		conflict = self.book(self.listed_room, request_anyway=1)
		self.assertEqual(self.as_user(self.approver_1, conflict, "resolve_conflict", "keep"), "Approved")
		self.assertEqual(frappe.db.get_value("Room Booking", requested.name, "status"), "Denied")
		self.assertEqual(self.open_todos(conflict), [])

	def test_keep_leaves_the_bookings_that_share_the_room_with_it(self):
		approved = self.book(self.listed_room, user=self.approver_1, as_user=True)
		kept = self.book(self.listed_room, request_anyway=1, can_share_room=1)
		sharing_conflict = self.book(self.listed_room, request_anyway=1, can_share_room=1)
		plain_conflict = self.book(self.listed_room, request_anyway=1)
		approved.status = "Cancelled"
		approved.save(ignore_permissions=True)
		sharing_request = self.book(self.listed_room, can_share_room=1)
		self.assertEqual(sharing_request.status, "Requested")

		self.assertEqual(self.as_user(self.approver_1, kept, "resolve_conflict", "keep"), "Approved")
		for booking, status in (
			(sharing_conflict, "Conflict"),
			(sharing_request, "Requested"),
			(plain_conflict, "Denied"),
		):
			self.assertEqual(frappe.db.get_value("Room Booking", booking.name, "status"), status)

	def test_keep_refuses_while_an_approved_booking_holds_the_time(self):
		self.book(self.listed_room, user=self.approver_1, as_user=True)
		conflict = self.book(self.listed_room, request_anyway=1)
		with self.assertRaisesRegex(ValidationError, "already booked"):
			self.as_user(self.approver_2, conflict, "resolve_conflict", "keep")

	def test_share_lets_both_bookings_hold_the_room(self):
		approved = self.book(self.listed_room, user=self.approver_1, as_user=True)
		conflict = self.book(self.listed_room, request_anyway=1)
		self.assertEqual(self.as_user(self.approver_2, conflict, "resolve_conflict", "share"), "Approved")
		self.assertEqual(frappe.db.get_value("Room Booking", approved.name, "status"), "Approved")
		for booking in (approved, conflict):
			self.assertTrue(frappe.db.get_value("Room Booking", booking.name, "can_share_room"))

	def test_only_an_approver_resolves_and_only_a_conflict(self):
		self.book(self.listed_room, user=self.approver_1, as_user=True)
		conflict = self.book(self.listed_room, request_anyway=1)
		with self.assertRaises(frappe.PermissionError):
			self.as_user(self.staff_a, conflict, "resolve_conflict", "keep")
		with self.assertRaises(ValidationError):
			self.as_user(self.approver_1, conflict, "resolve_conflict", "drop")
		with self.assertRaises(ValidationError):
			self.as_user(self.approver_1, self.book(self.listed_room, 11), "resolve_conflict", "keep")


class TestRoomBookingRace(FrappeTestCase):
	"""Two requests, each with its own connection, for one room at one time. Commits real data, deleted at the end."""

	def test_two_bookings_at_once_cannot_both_take_the_room(self):
		room = frappe.get_doc(
			{"doctype": "Room", "room_name": "_Test A1 Race Room", "is_bookable": 1}
		).insert(ignore_permissions=True)
		requester = make_person("_Test Room", "Racer").name
		frappe.db.commit()
		try:
			results = race_for_the_room(room.name, requester)
			self.assertEqual(len([result for result in results if isinstance(result, str)]), 1, results)
			self.assertEqual(frappe.db.count("Room Booking", {"room": room.name}), 1)
		finally:
			frappe.db.rollback()
			for name in frappe.get_all("Room Booking", {"room": room.name}, pluck="name"):
				frappe.delete_doc("Room Booking", name, force=True, ignore_permissions=True)
			frappe.delete_doc("Room", room.name, force=True, ignore_permissions=True)
			frappe.delete_doc("Person", requester, force=True, ignore_permissions=True)
			frappe.db.commit()


def race_for_the_room(room: str, requester: str) -> list:
	"""Book *room* twice at once, each in a thread with its own connection. Returns each name or error."""
	site, sites_path = frappe.local.site, frappe.local.sites_path
	# Each request reads before either commits, so a plain clash read would answer from a snapshot.
	barrier = threading.Barrier(2, timeout=30)
	results = []

	def book():
		frappe.init(site, sites_path=sites_path)
		frappe.connect()
		try:
			frappe.db.get_value("Room", room, "room_name")
			barrier.wait()
			booking = frappe.get_doc(
				{
					"doctype": "Room Booking",
					"room": room,
					"requester": requester,
					"purpose": "_Test race",
					"start_datetime": "2032-07-08 09:00:00",
					"end_datetime": "2032-07-08 10:00:00",
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()
			results.append(booking.name)
		except Exception as error:
			results.append(error)
		finally:
			frappe.destroy()

	threads = [threading.Thread(target=book) for _thread in range(2)]
	for thread in threads:
		thread.start()
	for thread in threads:
		thread.join(timeout=60)
	return results
