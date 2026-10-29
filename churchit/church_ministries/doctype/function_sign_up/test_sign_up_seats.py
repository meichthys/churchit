# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import threading
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, get_datetime, now_datetime

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CANCELLED,
	CONFIRMED,
	HOLD_HOURS,
	PENDING,
	WAITLISTED,
	get_function_item_totals,
	get_item_status,
)
from churchit.patches.v1_0 import add_sign_up_attendees
from churchit.tests.helpers import RollbackEachTest, ensure, make_function, make_person

SIGN_UP = "Function Sign-Up"


def make_sign_up(function, person=None, attendees=(), items=(), **values):
	"""A desk sign-up of *person* for *function*, with extra *attendees* rows and *items* (item, quantity)."""
	sign_up = frappe.get_doc({"doctype": SIGN_UP, "function": function, "person": person, **values})
	for attendee in attendees:
		sign_up.append("attendees", attendee)
	for item, quantity in items:
		sign_up.append("table_iprj", {"item": item, "my_quantity": quantity})
	return sign_up.insert(ignore_permissions=True)


def function_attendance(function):
	return {row.person: row.attendance_type for row in frappe.get_doc("Function", function).attendance}


class TestSignUpSeats(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.people = [make_person("_Test Seat", name).name for name in ("Ann", "Ben", "Cal", "Dee", "Eve")]
		cls.dish = ensure("Sign-Up Item", {"item": "_Test Seat Dish"})

	def make_function(self, **values):
		return make_function("_Test Seats", allow_sign_ups=1, **values)

	def test_the_registrant_attends_while_attending_is_ticked(self):
		function = self.make_function()
		sign_up = make_sign_up(function.name, self.people[0])
		self.assertEqual([row.person for row in sign_up.attendees], [self.people[0]])
		self.assertTrue(sign_up.attendees[0].attendee_name)

		sign_up.attending = 0
		sign_up.save(ignore_permissions=True)
		self.assertEqual(sign_up.attendees, [])

	def test_a_changed_registrant_takes_over_the_registrant_row(self):
		function = self.make_function(capacity=1)
		sign_up = make_sign_up(function.name, self.people[0])

		sign_up.person = self.people[1]
		sign_up.save(ignore_permissions=True)

		self.assertEqual([row.person for row in sign_up.attendees], [self.people[1]])
		self.assertEqual(function_attendance(function.name), {self.people[1]: "Signed-Up"})

		guest = make_sign_up(
			self.make_function().name, registrant_name="_Test Seat Nmae", email="_test_seat@example.com"
		)
		guest.registrant_name = "_Test Seat Name"
		guest.save(ignore_permissions=True)
		self.assertEqual([row.attendee_name for row in guest.attendees], ["_Test Seat Name"])

	def test_a_function_confirms_until_full_then_waits(self):
		function = self.make_function(capacity=2)
		first = make_sign_up(function.name, self.people[0])
		second = make_sign_up(function.name, self.people[1])
		third = make_sign_up(function.name, self.people[2])

		self.assertEqual([first.status, second.status, third.status], [CONFIRMED, CONFIRMED, WAITLISTED])

	def test_a_party_larger_than_the_capacity_is_refused(self):
		function = self.make_function(capacity=1)
		with self.assertRaises(frappe.ValidationError):
			make_sign_up(function.name, self.people[0], attendees=[{"person": self.people[1]}])

	def test_an_attendee_selection_must_be_one_of_the_functions(self):
		function = self.make_function(selections=[{"selection": "Adult"}])
		with self.assertRaises(frappe.ValidationError):
			make_sign_up(
				function.name, self.people[0], attendees=[{"person": self.people[0], "selection": "VIP"}]
			)
		with self.assertRaises(frappe.ValidationError):
			make_sign_up(function.name, self.people[0])  # the registrant's row has no selection

		sign_up = make_sign_up(
			function.name, self.people[0], attendees=[{"person": self.people[0], "selection": "Adult"}]
		)
		self.assertEqual([row.selection for row in sign_up.attendees], ["Adult"])

	def test_a_selection_fills_on_its_own(self):
		function = self.make_function(
			selections=[{"selection": "Child", "capacity": 1}, {"selection": "Adult"}]
		)
		child = {"attendee_name": "_Test Seat Kid", "selection": "Child"}
		make_sign_up(
			function.name,
			attendees=[child],
			attending=0,
			registrant_name="_Test Seat Parent",
			email="parent@example.com",
		)

		self.assertEqual(
			make_sign_up(
				function.name, self.people[0], attendees=[{"person": self.people[0], "selection": "Adult"}]
			).status,
			CONFIRMED,
		)
		self.assertEqual(
			make_sign_up(
				function.name, self.people[1], attendees=[{"person": self.people[1], "selection": "Child"}]
			).status,
			WAITLISTED,
		)

	def test_a_sign_up_over_a_limited_items_quantity_is_refused(self):
		function = self.make_function(table_cxhh=[{"item": self.dish, "quantity_needed": 3, "is_limited": 1}])
		make_sign_up(function.name, self.people[0], items=[(self.dish, 2)])
		with self.assertRaises(frappe.ValidationError):
			make_sign_up(function.name, self.people[1], items=[(self.dish, 2)])
		self.assertEqual(
			make_sign_up(function.name, self.people[1], items=[(self.dish, 1)]).status, CONFIRMED
		)

	def test_an_unlimited_item_takes_any_quantity(self):
		function = self.make_function(table_cxhh=[{"item": self.dish, "quantity_needed": 1}])
		make_sign_up(function.name, self.people[0], items=[(self.dish, 1)])
		self.assertEqual(
			make_sign_up(function.name, self.people[1], items=[(self.dish, 5)]).status, CONFIRMED
		)

	def test_an_items_only_sign_up_is_confirmed_when_the_function_is_full(self):
		function = self.make_function(capacity=1, table_cxhh=[{"item": self.dish, "quantity_needed": 5}])
		make_sign_up(function.name, self.people[0])
		bringer = make_sign_up(function.name, self.people[1], attending=0, items=[(self.dish, 2)])

		self.assertEqual(bringer.status, CONFIRMED)
		self.assertEqual(bringer.attendees, [])

	def test_only_sign_ups_that_hold_seats_count_their_items(self):
		function = self.make_function(capacity=1, table_cxhh=[{"item": self.dish, "quantity_needed": 5}])
		make_sign_up(function.name, self.people[0], items=[(self.dish, 1)])
		waiting = make_sign_up(function.name, self.people[1], items=[(self.dish, 4)])

		self.assertEqual(waiting.status, WAITLISTED)
		self.assertEqual(get_item_status(function.name, self.dish)["quantity_signed_up"], 1)
		self.assertEqual(get_function_item_totals(function.name)[self.dish]["quantity_signed_up"], 1)

	def test_an_amount_due_holds_the_seats_until_the_hold_expires(self):
		function = self.make_function(capacity=1, selections=[{"selection": "Adult", "price": 20}])
		adult = {"selection": "Adult"}
		held = make_sign_up(function.name, self.people[0], attendees=[{**adult, "person": self.people[0]}])

		self.assertEqual(held.status, PENDING)
		expected = add_to_date(now_datetime(), hours=HOLD_HOURS)
		self.assertLess(abs((get_datetime(held.hold_expires_on) - expected).total_seconds()), 60)
		self.assertEqual(
			make_sign_up(
				function.name, self.people[1], attendees=[{**adult, "person": self.people[1]}]
			).status,
			WAITLISTED,
		)

		frappe.db.set_value(SIGN_UP, held.name, "hold_expires_on", add_to_date(now_datetime(), hours=-1))
		self.assertEqual(
			make_sign_up(
				function.name, self.people[2], attendees=[{**adult, "person": self.people[2]}]
			).status,
			PENDING,
		)

	def test_a_confirmed_sign_up_cannot_grow_past_the_capacity(self):
		function = self.make_function(capacity=2)
		sign_up = make_sign_up(function.name, self.people[0])
		make_sign_up(function.name, self.people[1])

		sign_up.append("attendees", {"person": self.people[2]})
		with self.assertRaises(frappe.ValidationError):
			sign_up.save(ignore_permissions=True)

	def test_each_attendee_person_has_an_attendance_row_while_confirmed(self):
		function = self.make_function(capacity=2)
		guest = {"attendee_name": "_Test Seat Friend"}
		sign_up = make_sign_up(function.name, self.people[0], attendees=[{"person": self.people[1]}])
		waiting = make_sign_up(function.name, self.people[2], attendees=[guest])

		self.assertEqual(function_attendance(function.name), dict.fromkeys(self.people[:2], "Signed-Up"))
		self.assertEqual(waiting.status, WAITLISTED)

		sign_up.remove(next(row for row in sign_up.attendees if row.person == self.people[1]))
		sign_up.save(ignore_permissions=True)
		self.assertEqual(function_attendance(function.name), {self.people[0]: "Signed-Up"})

		sign_up.delete(ignore_permissions=True)
		self.assertNotIn(self.people[0], function_attendance(function.name))

	def test_a_person_is_signed_up_once_for_a_function(self):
		function = self.make_function()
		make_sign_up(function.name, self.people[0], attendees=[{"person": self.people[1]}])

		with self.assertRaises(frappe.ValidationError):
			make_sign_up(function.name, self.people[1])
		with self.assertRaises(frappe.ValidationError):
			make_sign_up(function.name, self.people[2], attendees=[{"person": self.people[1]}])
		with self.assertRaises(frappe.ValidationError):
			make_sign_up(
				function.name,
				self.people[3],
				attendees=[{"person": self.people[4]}, {"person": self.people[4]}],
			)

	def test_the_patch_adds_the_attending_person_once(self):
		function = self.make_function()
		attending = make_sign_up(function.name, self.people[0])
		items_only = make_sign_up(function.name, self.people[1], attending=0)
		frappe.db.delete("Function Sign-Up Attendee", {"parent": attending.name})

		add_sign_up_attendees.execute()
		add_sign_up_attendees.execute()

		attending.reload()
		items_only.reload()
		self.assertEqual([row.person for row in attending.attendees], [self.people[0]])
		self.assertEqual(items_only.attendees, [])

	def test_a_sign_up_moved_into_a_full_function_waits(self):
		full, other = self.make_function(capacity=1), self.make_function(capacity=1)
		make_sign_up(full.name, self.people[0])
		moving = make_sign_up(other.name, self.people[1])
		waiting = make_sign_up(other.name, self.people[2])

		moving.function = full.name
		moving.save(ignore_permissions=True)

		self.assertEqual(moving.status, WAITLISTED)
		self.assertEqual(frappe.db.get_value(SIGN_UP, waiting.name, "status"), CONFIRMED)
		self.assertEqual(function_attendance(full.name), {self.people[0]: "Signed-Up"})
		self.assertEqual(function_attendance(other.name), {self.people[2]: "Signed-Up"})

	def test_a_cancelled_sign_up_leaves_the_persons_later_sign_up_alone(self):
		function = self.make_function()
		cancelled = make_sign_up(function.name, self.people[0])
		cancelled.cancel_registration()
		make_sign_up(function.name, self.people[0])

		cancelled.notes = "_Test note"
		cancelled.save(ignore_permissions=True)
		self.assertEqual(function_attendance(function.name), {self.people[0]: "Signed-Up"})

		cancelled.delete(ignore_permissions=True)
		self.assertEqual(function_attendance(function.name), {self.people[0]: "Signed-Up"})

	def test_a_sign_up_cancels_after_its_function_adds_selections(self):
		function = self.make_function()
		sign_up = make_sign_up(function.name, self.people[0])
		function.reload()
		function.append("selections", {"selection": "Adult"})
		function.save(ignore_permissions=True)

		sign_up.cancel_registration()
		self.assertEqual(sign_up.status, CANCELLED)

	def test_a_held_sign_up_that_grows_keeps_its_hold(self):
		function = self.make_function(selections=[{"selection": "Adult", "price": 20}])
		adult = {"selection": "Adult"}
		held = make_sign_up(function.name, self.people[0], attendees=[{**adult, "person": self.people[0]}])
		hold = get_datetime(held.hold_expires_on)

		held.append("attendees", {**adult, "person": self.people[1]})
		held.save(ignore_permissions=True)
		self.assertEqual((held.status, get_datetime(held.hold_expires_on)), (PENDING, hold))

	def test_a_paid_sign_up_cannot_grow_into_a_balance(self):
		function = self.make_function(selections=[{"selection": "Adult", "price": 10}])
		adult = {"selection": "Adult"}
		paid = make_sign_up(function.name, self.people[0], attendees=[{**adult, "person": self.people[0]}])
		paid_values = {
			"status": CONFIRMED,
			"hold_expires_on": None,
			"amount_paid": 10,
			"payment_status": "Paid",
		}
		frappe.db.set_value(SIGN_UP, paid.name, paid_values)
		paid.reload()

		paid.append("attendees", {**adult, "person": self.people[1]})
		with self.assertRaises(frappe.ValidationError):
			paid.save(ignore_permissions=True)


class TestSignUpSeatRace(FrappeTestCase):
	"""Two requests, each with its own connection, for the last seat. Commits real data, deleted at the end."""

	def test_two_requests_for_the_last_seat_confirm_one(self):
		function = make_function("_Test Seat Race", allow_sign_ups=1, capacity=1).name
		people = [make_person("_Test Seat Racer", name).name for name in ("Fay", "Gus")]
		frappe.db.commit()
		try:
			statuses = race_for_seats(function, people)
			self.assertCountEqual(statuses, [CONFIRMED, WAITLISTED])
		finally:
			delete_race_data(function, people)

	def test_two_requests_for_the_same_person_sign_up_once(self):
		function = make_function("_Test Seat Race", allow_sign_ups=1).name
		person = make_person("_Test Seat Racer", "Hal").name
		frappe.db.commit()
		try:
			statuses = race_for_seats(function, [person, person])
			self.assertEqual(statuses.count(CONFIRMED), 1)
			self.assertIsInstance(
				next(status for status in statuses if status != CONFIRMED), frappe.ValidationError
			)
		finally:
			delete_race_data(function, [person])


def delete_race_data(function: str, people: list[str]) -> None:
	frappe.db.rollback()
	records = [(SIGN_UP, name) for name in frappe.get_all(SIGN_UP, {"function": function}, pluck="name")]
	for doctype, name in [*records, ("Function", function), *(("Person", person) for person in people)]:
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, delete_permanently=True)
	frappe.db.commit()


def race_for_seats(function: str, people: list[str]) -> list:
	"""Sign each of *people* up at once, each in a thread with its own connection. Returns each status."""
	site, sites_path = frappe.local.site, frappe.local.sites_path
	# Each request reads before either commits, so a plain count would answer from a snapshot without the other.
	barrier = threading.Barrier(len(people), timeout=30)
	statuses = []

	def sign_up(person):
		frappe.init(site, sites_path=sites_path)
		frappe.connect()
		try:
			frappe.db.get_value("Function", function, "capacity")
			barrier.wait()
			statuses.append(make_sign_up(function, person).status)
			frappe.db.commit()
		except Exception as error:
			statuses.append(error)
		finally:
			frappe.destroy()

	threads = [threading.Thread(target=sign_up, args=(person,)) for person in people]
	for thread in threads:
		thread.start()
	for thread in threads:
		thread.join(timeout=60)
	return statuses
