# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import threading
import time
from unittest.mock import patch

import frappe
from frappe.client import insert as insert_doc
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.church_access import set_user_church
from churchit.church_operations.doctype.room_booking.room_booking import RoomBooking
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches


def make_asset(title, is_bookable=1, **values):
	return (
		frappe.get_doc({"doctype": "Church Asset", "title": title, "is_bookable": is_bookable, **values})
		.insert(ignore_permissions=True)
		.name
	)


def make_booking(assets, hour=9, room=None, **values):
	"""A Room Booking of *assets* (and *room*, if given) from *hour* for one hour."""
	return frappe.get_doc(
		{
			"doctype": "Room Booking",
			"room": room,
			"purpose": "_Test equipment",
			"start_datetime": f"2035-05-05 {hour:02d}:00:00",
			"end_datetime": f"2035-05-05 {hour + 1:02d}:00:00",
			"assets": [{"asset": asset} for asset in assets],
			**values,
		}
	)


def delete_bookings(assets):
	frappe.set_user("Administrator")
	bookings = frappe.get_all(
		"Room Booking Asset", filters={"asset": ["in", assets]}, pluck="parent", distinct=True
	)
	for name in bookings:
		frappe.delete_doc("Room Booking", name, force=True, ignore_permissions=True)


class TestRoomBookingAssets(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.requester = make_person("_Test Asset", "Booker").name
		cls.projector = make_asset("_Test Asset Projector")
		cls.speaker = make_asset("_Test Asset Speaker")
		cls.stored = make_asset("_Test Asset Stored", is_bookable=0)

	def tearDown(self):
		delete_bookings([self.projector, self.speaker, self.stored])
		super().tearDown()

	def book(self, assets, hour=9, **values):
		return make_booking(assets, hour, requester=self.requester, **values).insert(ignore_permissions=True)

	def test_a_booking_of_no_room_and_no_asset_is_refused(self):
		with self.assertRaises(frappe.MandatoryError):
			self.book([])

	def test_an_asset_that_is_not_bookable_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "not bookable"):
			self.book([self.stored])

	def test_a_conflict_booking_holds_its_asset(self):
		self.book([self.projector], status="Conflict")
		with self.assertRaisesRegex(frappe.ValidationError, "already booked"):
			self.book([self.projector])

	def test_a_booking_of_assets_and_no_room_is_approved(self):
		booking = self.book([self.projector])
		self.assertEqual(booking.status, "Approved")
		self.assertFalse(booking.room)

	def test_an_asset_booked_at_the_same_time_is_refused(self):
		self.book([self.projector], hour=9)
		with self.assertRaisesRegex(frappe.ValidationError, "already booked"):
			self.book([self.speaker, self.projector], hour=9)

		self.book([self.projector], hour=10)
		self.book([self.speaker], hour=9)

	def test_a_denied_or_cancelled_booking_does_not_hold_its_asset(self):
		self.book([self.projector], status="Denied")
		self.book([self.projector], hour=9, status="Cancelled")
		self.assertEqual(self.book([self.projector]).status, "Approved")

	def test_bookings_of_other_assets_and_no_room_at_one_time_do_not_clash(self):
		"""Sent as REST does, with an empty room, so the room clash must not compare empty rooms."""
		for asset in (self.projector, self.speaker):
			insert_doc(
				{
					"doctype": "Room Booking",
					"room": "",
					"requester": self.requester,
					"purpose": "_Test equipment",
					"start_datetime": "2035-05-05 09:00:00",
					"end_datetime": "2035-05-05 10:00:00",
					"assets": [{"asset": asset}],
				}
			)

	def test_an_asset_that_stopped_being_bookable_keeps_its_booking(self):
		booking = self.book([self.speaker])
		frappe.db.set_value("Church Asset", self.speaker, "is_bookable", 0)
		booking.notes = "Bring the cables"
		booking.save(ignore_permissions=True)

		booking.start_datetime = "2035-05-05 08:00:00"
		with self.assertRaisesRegex(frappe.ValidationError, "not bookable"):
			booking.save(ignore_permissions=True)


class TestRoomBookingAssetsAcrossChurches(RollbackEachTest):
	"""An asset is booked only by its own church, and a shared one by every church."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.staff_b = ensure_user("_test_asset_staff_b@example.com", "Asset Staff B", roles=("Church Staff",))
		set_user_church(cls.staff_b, cls.branch_b)
		cls.requester_a = make_person("_Test Asset", "Requester A", church=cls.branch_a).name
		cls.requester_b = make_person("_Test Asset", "Requester B", church=cls.branch_b).name
		cls.asset_a = make_asset("_Test Asset Of A", church=cls.branch_a)
		cls.asset_b = make_asset("_Test Asset Of B", church=cls.branch_b)
		cls.shared_asset = make_asset("_Test Asset Shared", church=cls.branch_a, is_shared=1)

	def tearDown(self):
		delete_bookings([self.asset_a, self.asset_b, self.shared_asset])
		super().tearDown()

	def book(self, assets, requester=None):
		return make_booking(assets, requester=requester or self.requester_b)

	def test_a_booking_with_no_room_takes_the_users_church(self):
		frappe.set_user(self.staff_b)
		booking = self.book([self.asset_b]).insert()
		self.assertEqual((booking.status, booking.church), ("Approved", self.branch_b))

	def test_an_asset_of_another_church_is_refused(self):
		frappe.set_user(self.staff_b)
		with self.assertRaises(frappe.PermissionError):
			self.book([self.asset_a]).insert()

	def test_an_unbookable_asset_of_another_church_keeps_its_title_hidden(self):
		hidden = make_asset("_Test Asset Hidden Title Of A", is_bookable=0, church=self.branch_a)
		frappe.set_user(self.staff_b)
		with self.assertRaises(frappe.PermissionError) as refusal:
			self.book([hidden]).insert()
		self.assertNotIn("Hidden Title", str(refusal.exception))

	def test_every_church_books_a_shared_asset(self):
		frappe.set_user(self.staff_b)
		self.assertEqual(self.book([self.shared_asset]).insert().church, self.branch_b)

	def test_a_shared_asset_clash_names_no_booking_of_another_church(self):
		theirs = self.book([self.shared_asset], requester=self.requester_a).insert(ignore_permissions=True)
		theirs.db_set("church", self.branch_a)

		frappe.set_user(self.staff_b)
		with self.assertRaises(frappe.ValidationError) as clash:
			self.book([self.shared_asset]).insert()
		self.assertNotIn(theirs.name, str(clash.exception))
		self.assertIn("1 booking(s) of another church", str(clash.exception))

		frappe.set_user("Administrator")
		theirs.db_set("church", self.branch_b)
		frappe.set_user(self.staff_b)
		with self.assertRaisesRegex(frappe.ValidationError, theirs.name):
			self.book([self.shared_asset]).insert()


class TestRoomBookingAssetRace(FrappeTestCase):
	"""Two requests, each with its own connection, for one asset. Commits real data, deleted at the end."""

	def test_two_bookings_of_one_asset_at_once_save_one(self):
		asset = make_asset("_Test Asset Race")
		requester = make_person("_Test Asset", "Racer").name
		frappe.db.commit()
		try:
			results = race_for_asset(asset, requester)
			self.assertEqual(sum(isinstance(result, str) for result in results), 1, results)
			self.assertIsInstance(
				next(result for result in results if not isinstance(result, str)), frappe.ValidationError
			)
		finally:
			frappe.db.rollback()
			delete_bookings([asset])
			frappe.delete_doc("Church Asset", asset, force=True, ignore_permissions=True)
			frappe.delete_doc("Person", requester, force=True, ignore_permissions=True)
			frappe.db.commit()

	def test_a_room_booking_and_an_equipment_booking_at_once_both_save(self):
		"""They clash in nothing, so neither may fail on the other's locks."""
		taken, wanted = make_asset("_Test Asset Lock Taken"), make_asset("_Test Asset Lock Wanted")
		room = frappe.get_doc({"doctype": "Room", "room_name": "_Test Asset Lock Room", "is_bookable": 1})
		room = room.insert(ignore_permissions=True).name
		requester = make_person("_Test Asset", "Locker").name
		another_day = {"start_datetime": "2035-06-06 09:00:00", "end_datetime": "2035-06-06 10:00:00"}
		make_booking([taken], requester=requester, **another_day).insert(ignore_permissions=True)
		booking = make_booking([wanted], room=room, requester=requester).insert(ignore_permissions=True)
		frappe.db.commit()
		try:
			results = move_and_book_at_once(booking.name, taken, requester)
			self.assertTrue(all(isinstance(result, str) for result in results), results)
		finally:
			frappe.db.rollback()
			delete_bookings([taken, wanted])
			frappe.delete_doc("Room", room, force=True, ignore_permissions=True)
			for asset in (taken, wanted):
				frappe.delete_doc("Church Asset", asset, force=True, ignore_permissions=True)
			frappe.delete_doc("Person", requester, force=True, ignore_permissions=True)
			frappe.db.commit()


class TestRoomBookingEditRace(FrappeTestCase):
	"""Two edits of stored bookings at once, each with its own connection. Commits real data, deleted at the end."""

	def setUp(self):
		self.assets = [make_asset("_Test Edit Race 1"), make_asset("_Test Edit Race 2")]
		self.rooms = [
			frappe.get_doc(
				{"doctype": "Room", "room_name": f"_Test Edit Race Room {number}", "is_bookable": 1}
			)
			.insert(ignore_permissions=True)
			.name
			for number in (1, 2)
		]
		self.requester = make_person("_Test Edit", "Racer").name

	def tearDown(self):
		frappe.db.rollback()
		for name in frappe.get_all("Room Booking", {"room": ["in", self.rooms]}, pluck="name"):
			frappe.delete_doc("Room Booking", name, force=True, ignore_permissions=True)
		delete_bookings(self.assets)
		for name in self.rooms:
			frappe.delete_doc("Room", name, force=True, ignore_permissions=True)
		for name in self.assets:
			frappe.delete_doc("Church Asset", name, force=True, ignore_permissions=True)
		frappe.delete_doc("Person", self.requester, force=True, ignore_permissions=True)
		frappe.db.commit()

	def book(self, assets=(), room=None, hour=9):
		booking = make_booking(list(assets), hour, room=room, requester=self.requester)
		return booking.insert(ignore_permissions=True).name

	def assert_both_save(self, bookings):
		frappe.db.commit()
		self.assertEqual(edit_at_once(bookings), [None, None])

	def test_edits_of_bookings_of_other_equipment_at_once_both_save(self):
		self.assert_both_save([self.book([self.assets[0]]), self.book([self.assets[1]])])

	def test_edits_of_two_bookings_of_one_asset_at_once_both_save(self):
		self.assert_both_save([self.book([self.assets[0]], hour=9), self.book([self.assets[0]], hour=11)])

	def test_edits_of_bookings_of_other_rooms_at_once_both_save(self):
		self.assert_both_save([self.book(room=self.rooms[0]), self.book(room=self.rooms[1])])

	def test_edits_of_two_bookings_of_one_room_at_once_both_save(self):
		self.assert_both_save([self.book(room=self.rooms[0], hour=9), self.book(room=self.rooms[0], hour=11)])


def move_and_book_at_once(room_booking: str, asset: str, requester: str) -> list:
	"""Move *room_booking* (a room and equipment) an hour, and book *asset* alone, in two threads.

	Each thread has its own connection. The move reaches its equipment check holding its room clash
	locks, and the new booking then starts its own check. Returns each booking's name or error.
	"""
	site, sites_path = frappe.local.site, frappe.local.sites_path
	room_is_waiting, equipment_is_checking = threading.Event(), threading.Event()
	check_asset_conflicts = RoomBooking.check_asset_conflicts
	results = []

	def check_in_turn(booking):
		if booking.room:
			room_is_waiting.set()
			equipment_is_checking.wait(20)
			time.sleep(2)
		else:
			room_is_waiting.wait(20)
			equipment_is_checking.set()
		check_asset_conflicts(booking)

	def save(get_booking):
		frappe.init(site, sites_path=sites_path)
		frappe.connect()
		try:
			results.append(get_booking().save(ignore_permissions=True).name)
			frappe.db.commit()
		except Exception as error:
			results.append(error)
		finally:
			frappe.destroy()

	def get_moved_booking():
		booking = frappe.get_doc("Room Booking", room_booking)
		booking.start_datetime, booking.end_datetime = "2035-05-05 11:00:00", "2035-05-05 12:00:00"
		return booking

	with patch.object(RoomBooking, "check_asset_conflicts", check_in_turn):
		threads = [
			threading.Thread(target=save, args=(get_moved_booking,)),
			threading.Thread(target=save, args=(lambda: make_booking([asset], requester=requester),)),
		]
		for thread in threads:
			thread.start()
		for thread in threads:
			thread.join(timeout=60)
	return results


def race_for_asset(asset: str, requester: str) -> list:
	"""Book *asset* twice at once, each in a thread with its own connection. Returns each name or error."""
	site, sites_path = frappe.local.site, frappe.local.sites_path
	# Each request reads before either commits, so a plain clash read would answer from an older snapshot.
	barrier = threading.Barrier(2, timeout=30)
	results = []

	def book():
		frappe.init(site, sites_path=sites_path)
		frappe.connect()
		try:
			frappe.db.get_value("Church Asset", asset, "title")
			barrier.wait()
			results.append(make_booking([asset], requester=requester).insert(ignore_permissions=True).name)
			frappe.db.commit()
		except Exception as error:
			results.append(error)
		finally:
			frappe.destroy()

	threads = [threading.Thread(target=book) for _ in range(2)]
	for thread in threads:
		thread.start()
	for thread in threads:
		thread.join(timeout=60)
	return results


def edit_at_once(bookings: list[str]) -> list:
	"""Edit the purpose of each of *bookings* in its own thread and connection. Returns None, the error or "not finished" for each.

	Each save waits in validate, up to 2 seconds, for the others to reach validate too, so that each holds
	its own row (Frappe locks it before validate) when the clash checks run.
	"""
	site, sites_path = frappe.local.site, frappe.local.sites_path
	in_validate = {name: threading.Event() for name in bookings}
	validate = RoomBooking.validate
	results = {}

	def validate_in_turn(booking):
		in_validate[booking.name].set()
		for event in in_validate.values():
			event.wait(2)
		validate(booking)

	def edit(name):
		frappe.init(site, sites_path=sites_path)
		frappe.connect()
		try:
			booking = frappe.get_doc("Room Booking", name)
			booking.purpose = "_Test edited at once"
			booking.save(ignore_permissions=True)
			frappe.db.commit()
			results[name] = None
		except Exception as error:
			results[name] = error
		finally:
			frappe.destroy()

	with patch.object(RoomBooking, "validate", validate_in_turn):
		threads = [threading.Thread(target=edit, args=(name,)) for name in bookings]
		for thread in threads:
			thread.start()
		for thread in threads:
			thread.join(timeout=60)
	return [results.get(name, "not finished") for name in bookings]
