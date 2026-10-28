# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import threading

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.church_access import set_user_church
from churchit.church_operations.doctype.room_booking.test_room_booking_assets import (
	delete_bookings,
	make_asset,
	make_booking,
)
from churchit.church_operations.report.assets_on_loan import assets_on_loan
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches


class TestRoomBookingLoans(RollbackEachTest):
	"""A loan is an Approved booking of equipment that a Church Manager checks out and in."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		users = {
			"manager_a": ("Church Manager", cls.branch_a),
			"manager_b": ("Church Manager", cls.branch_b),
			"user_a": ("Church User", cls.branch_a),
		}
		for key, (role, church) in users.items():
			user = ensure_user(f"_test_loan_{key}@example.com", key, roles=(role,))
			set_user_church(user, church)
			setattr(cls, key, user)
		cls.requester_a = make_person("_Test Loan", "Requester A", church=cls.branch_a).name
		cls.requester_b = make_person("_Test Loan", "Requester B", church=cls.branch_b).name
		cls.camera = make_asset("_Test Loan Camera", church=cls.branch_a)
		cls.shared_tent = make_asset("_Test Loan Shared Tent", church=cls.branch_a, is_shared=1)
		cls.gated_room, cls.open_room = (
			frappe.get_doc(
				{"doctype": "Room", "room_name": name, "is_bookable": 1, "church": cls.branch_a, **values}
			)
			.insert(ignore_permissions=True)
			.name
			for name, values in (("_Test Loan Gated Room", {"requires_approval": 1}), ("_Test Loan Room", {}))
		)

	def tearDown(self):
		delete_bookings([self.camera, self.shared_tent])
		super().tearDown()

	def lend(self, assets=None, hour=9, church=None, **values):
		"""A booking of *assets* (the camera when not given) from *hour*, inserted with ignore_permissions."""
		frappe.set_user("Administrator")
		try:
			values.setdefault("requester", self.requester_a)
			return make_booking(
				[self.camera] if assets is None else assets, hour, church=church or self.branch_a, **values
			).insert(ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")

	def as_user(self, user, booking, method):
		"""Run *method* of *booking* as *user* on a fresh copy, and return the stored booking."""
		frappe.set_user(user)
		try:
			getattr(frappe.get_doc("Room Booking", booking.name), method)()
		finally:
			frappe.set_user("Administrator")
		return frappe.get_doc("Room Booking", booking.name)

	def test_check_out_refuses_a_requested_booking_and_one_with_no_equipment(self):
		requested = self.lend(room=self.gated_room)
		self.assertEqual(requested.status, "Requested")
		room_only = self.lend([], hour=11, room=self.open_room)
		self.assertEqual(room_only.status, "Approved")

		for booking in (requested, room_only):
			with self.assertRaisesRegex(frappe.ValidationError, "Only an Approved booking of equipment"):
				self.as_user(self.manager_a, booking, "check_out")
			self.assertFalse(frappe.db.get_value("Room Booking", booking.name, "checked_out_on"))

	def test_check_out_and_check_in_record_the_loan(self):
		loan = self.as_user(self.manager_a, self.lend(), "check_out")
		self.assertTrue(loan.checked_out_on)
		self.assertEqual((loan.status, loan.returned_on), ("Approved", None))
		with self.assertRaisesRegex(frappe.ValidationError, "already checked out"):
			self.as_user(self.manager_a, loan, "check_out")

		loan = self.as_user(self.manager_a, loan, "check_in")
		self.assertTrue(loan.returned_on)
		self.assertEqual(loan.status, "Completed")
		with self.assertRaisesRegex(frappe.ValidationError, "not returned"):
			self.as_user(self.manager_a, loan, "check_in")

	def test_check_in_refuses_a_booking_that_was_never_checked_out(self):
		booking = self.lend()
		with self.assertRaisesRegex(frappe.ValidationError, "not returned"):
			self.as_user(self.manager_a, booking, "check_in")
		self.assertEqual(frappe.db.get_value("Room Booking", booking.name, "status"), "Approved")

	def test_a_church_user_who_owns_the_booking_cannot_check_it_out_or_in(self):
		# A member asks for no equipment, so staff added it to the member's own booking.
		booking = self.lend()
		booking.db_set("owner", self.user_a)
		with self.assertRaises(frappe.PermissionError):
			self.as_user(self.user_a, booking, "check_out")

		self.as_user(self.manager_a, booking, "check_out")
		with self.assertRaises(frappe.PermissionError):
			self.as_user(self.user_a, booking, "check_in")

	def test_the_loan_times_can_be_set_only_by_check_out_and_check_in(self):
		loan = self.as_user(self.manager_a, self.lend(), "check_out")
		loan.db_set("owner", self.user_a)
		own_booking = self.lend(hour=11)
		own_booking.db_set("owner", self.user_a)
		refusal = "Only Check Out and Check In"

		frappe.set_user(self.user_a)
		try:
			for name, values in (
				(loan.name, {"returned_on": frappe.utils.now_datetime()}),
				(loan.name, {"checked_out_on": None}),
				(own_booking.name, {"checked_out_on": frappe.utils.now_datetime()}),
			):
				booking = frappe.get_doc("Room Booking", name).update(values)
				with self.assertRaisesRegex(frappe.PermissionError, refusal):
					booking.save()

			frappe.set_user(self.manager_a)
			with self.assertRaisesRegex(frappe.PermissionError, refusal):
				make_booking(
					[self.shared_tent],
					13,
					church=self.branch_a,
					requester=self.requester_a,
					checked_out_on=frappe.utils.now_datetime(),
				).insert()
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(
			frappe.db.get_value("Room Booking", loan.name, ["checked_out_on", "returned_on"]),
			(loan.checked_out_on, None),
		)

	def test_equipment_still_out_cannot_be_added_to_a_loan_that_is_out(self):
		overdue = self.as_user(self.manager_a, self.lend(hour=9), "check_out")
		later = self.as_user(self.manager_a, self.lend([self.shared_tent], hour=11), "check_out")

		frappe.set_user(self.manager_a)
		try:
			later.append("assets", {"asset": self.camera})
			with self.assertRaisesRegex(frappe.ValidationError, f"still out.*{overdue.name}"):
				later.save()
		finally:
			frappe.set_user("Administrator")

	def test_a_manager_of_another_church_cannot_check_a_loan_out_or_in(self):
		booking = self.lend()
		with self.assertRaises(frappe.PermissionError):
			self.as_user(self.manager_b, booking, "check_out")

		self.as_user(self.manager_a, booking, "check_out")
		with self.assertRaises(frappe.PermissionError):
			self.as_user(self.manager_b, booking, "check_in")

	def test_equipment_still_out_on_an_overdue_loan_cannot_be_checked_out_again(self):
		overdue = self.as_user(self.manager_a, self.lend(hour=9), "check_out")
		later = self.lend(hour=11)
		with self.assertRaisesRegex(frappe.ValidationError, f"still out.*{overdue.name}"):
			self.as_user(self.manager_a, later, "check_out")

		self.as_user(self.manager_a, overdue, "check_in")
		self.assertTrue(self.as_user(self.manager_a, later, "check_out").checked_out_on)

	def test_a_shared_asset_out_with_another_church_is_refused_without_naming_its_loan(self):
		theirs = self.as_user(self.manager_a, self.lend([self.shared_tent], hour=9), "check_out")
		mine = self.lend([self.shared_tent], hour=11, church=self.branch_b, requester=self.requester_b)

		with self.assertRaises(frappe.ValidationError) as refusal:
			self.as_user(self.manager_b, mine, "check_out")
		self.assertNotIn(theirs.name, str(refusal.exception))
		self.assertIn("1 booking(s) of another church", str(refusal.exception))

	def test_a_completed_loan_holds_neither_its_room_nor_its_equipment(self):
		loan = self.as_user(self.manager_a, self.lend(room=self.open_room), "check_out")
		self.as_user(self.manager_a, loan, "check_in")
		self.assertEqual(self.lend(room=self.open_room).status, "Approved")

		loan = frappe.get_doc("Room Booking", loan.name)
		loan.notes = "Returned with a scratch"
		loan.save(ignore_permissions=True)

	def test_assets_on_loan_lists_unreturned_loans_of_the_readers_church_overdue_first(self):
		returned = self.as_user(self.manager_a, self.lend([self.shared_tent], hour=13), "check_out")
		self.as_user(self.manager_a, returned, "check_in")
		self.lend([self.shared_tent], hour=15)
		later = self.as_user(self.manager_a, self.lend(hour=11), "check_out")
		overdue = self.as_user(self.manager_a, self.lend([self.shared_tent], hour=9), "check_out")

		rows = self.loan_report_as(self.manager_a)
		loans = [(row.name, row.asset) for row in rows if row.asset in (self.camera, self.shared_tent)]
		self.assertEqual(loans, [(overdue.name, self.shared_tent), (later.name, self.camera)])
		titles = {row._asset_link_title for row in rows if row.name == overdue.name}
		self.assertEqual(titles, {"_Test Loan Shared Tent"})

		self.assertFalse(
			{overdue.name, later.name} & {row.name for row in self.loan_report_as(self.manager_b)}
		)

	def loan_report_as(self, user):
		frappe.set_user(user)
		try:
			return assets_on_loan.execute()[1]
		finally:
			frappe.set_user("Administrator")


class TestRoomBookingLoanRace(FrappeTestCase):
	"""Two check outs of one asset at once, each with its own connection. Commits real data, deleted at the end."""

	def test_two_loans_of_one_asset_checked_out_at_once_lend_it_once(self):
		asset = make_asset("_Test Loan Race")
		requester = make_person("_Test Loan", "Racer").name
		bookings = [
			make_booking([asset], hour, requester=requester).insert(ignore_permissions=True).name
			for hour in (9, 11)
		]
		frappe.db.commit()
		try:
			results = check_out_at_once(bookings)
			self.assertEqual(sum(result is None for result in results), 1, results)
			# The guard refuses the loser, not a deadlock.
			self.assertIsInstance(
				next(result for result in results if result is not None), frappe.ValidationError
			)
			out = frappe.get_all(
				"Room Booking", filters={"name": ["in", bookings], "checked_out_on": ["is", "set"]}
			)
			self.assertEqual(len(out), 1)
		finally:
			frappe.db.rollback()
			delete_bookings([asset])
			frappe.delete_doc("Church Asset", asset, force=True, ignore_permissions=True)
			frappe.delete_doc("Person", requester, force=True, ignore_permissions=True)
			frappe.db.commit()


def check_out_at_once(bookings: list[str]) -> list:
	"""Check out each of *bookings* in its own thread and connection. Returns None or the error for each."""
	site, sites_path = frappe.local.site, frappe.local.sites_path
	# Each request reads its booking before either commits, so a plain read would answer from an older snapshot.
	barrier = threading.Barrier(len(bookings), timeout=30)
	results = []

	def check_out(name):
		frappe.init(site, sites_path=sites_path)
		frappe.connect()
		try:
			booking = frappe.get_doc("Room Booking", name)
			barrier.wait()
			booking.check_out()
			frappe.db.commit()
			results.append(None)
		except Exception as error:
			results.append(error)
		finally:
			frappe.destroy()

	threads = [threading.Thread(target=check_out, args=(name,)) for name in bookings]
	for thread in threads:
		thread.start()
	for thread in threads:
		thread.join(timeout=60)
	return results
