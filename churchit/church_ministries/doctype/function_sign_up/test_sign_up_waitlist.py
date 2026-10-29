# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import call, patch

import frappe
from frappe.utils import add_to_date, now_datetime

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CANCELLED,
	CONFIRMED,
	PENDING,
	WAITLISTED,
	FunctionSignUp,
	release_expired_holds,
)
from churchit.church_ministries.doctype.function_sign_up.test_sign_up_seats import make_sign_up
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_function, make_person

SIGN_UP = "Function Sign-Up"
PROMOTE = "churchit.church_ministries.doctype.function_sign_up.function_sign_up.promote_waitlist"


def status_of(sign_up):
	return frappe.db.get_value(SIGN_UP, sign_up.name, "status")


def run_promotion_now(method, **kwargs):
	"""In place of frappe.enqueue: promote the waitlist at once, and queue nothing else."""
	if method == PROMOTE:
		frappe.get_attr(method)(function=kwargs["function"])


class TestSignUpWaitlist(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.people = [
			make_person("_Test Waiting", name).name for name in ("Ann", "Ben", "Cal", "Dee", "Eve", "Fay")
		]

	def make_function(self, **values):
		return make_function("_Test Waitlist", allow_sign_ups=1, **values)

	def party(self, function, registrant, *others):
		return make_sign_up(function, registrant, attendees=[{"person": person} for person in others])

	def test_with_no_capacity_nobody_waits(self):
		function = self.make_function()
		statuses = {self.party(function.name, person).status for person in self.people}
		self.assertEqual(statuses, {CONFIRMED})

	def test_the_whole_party_waits_together(self):
		function = self.make_function(capacity=2)
		self.party(function.name, self.people[0])
		waiting = self.party(function.name, self.people[1], self.people[2])

		self.assertEqual(waiting.status, WAITLISTED)
		self.assertFalse(waiting.hold_expires_on)
		attendance = {row.person for row in frappe.get_doc("Function", function.name).attendance}
		self.assertEqual(attendance, {self.people[0]})

	def test_a_cancelled_seat_goes_to_the_oldest_party_that_fits(self):
		function = self.make_function(capacity=3)
		first, second, third = (self.party(function.name, person) for person in self.people[:3])
		pair = self.party(function.name, self.people[3], self.people[4])
		single = self.party(function.name, self.people[5])

		with patch.object(FunctionSignUp, "send_confirmation", autospec=True) as send_confirmation:
			first.cancel_registration()

		self.assertEqual([status_of(pair), status_of(single)], [WAITLISTED, CONFIRMED])
		# One save of the promoted sign-up, so the confirmation follows its status change once.
		saves = [call.args[0].name for call in send_confirmation.call_args_list]
		self.assertEqual(saves.count(single.name), 1)

		second.cancel_registration()
		self.assertEqual(status_of(pair), WAITLISTED)
		third.cancel_registration()
		self.assertEqual(status_of(pair), CONFIRMED)

	def test_a_promoted_party_with_an_amount_due_gets_a_hold(self):
		function = self.make_function(capacity=1, selections=[{"selection": "Adult", "price": 15}])
		first = make_sign_up(
			function.name, self.people[0], attendees=[{"person": self.people[0], "selection": "Adult"}]
		)
		waiting = make_sign_up(
			function.name, self.people[1], attendees=[{"person": self.people[1], "selection": "Adult"}]
		)
		self.assertEqual([first.status, waiting.status], [PENDING, WAITLISTED])

		first.cancel_registration()
		waiting.reload()
		self.assertEqual(waiting.status, PENDING)
		self.assertTrue(waiting.hold_expires_on)

	def test_deleting_a_sign_up_gives_its_seats_to_the_waitlist(self):
		function = self.make_function(capacity=1)
		first = self.party(function.name, self.people[0])
		waiting = self.party(function.name, self.people[1])

		first.delete(ignore_permissions=True)
		self.assertEqual(status_of(waiting), CONFIRMED)

	def test_a_smaller_party_gives_its_seats_to_the_waitlist(self):
		function = self.make_function(capacity=2)
		first = self.party(function.name, self.people[0], self.people[1])
		waiting = self.party(function.name, self.people[2])

		first.remove(next(row for row in first.attendees if row.person == self.people[1]))
		first.save(ignore_permissions=True)
		self.assertEqual(status_of(waiting), CONFIRMED)

	def test_an_expired_hold_is_released_by_the_cron(self):
		function = self.make_function(capacity=1, selections=[{"selection": "Adult", "price": 15}])
		held = make_sign_up(
			function.name, self.people[0], attendees=[{"person": self.people[0], "selection": "Adult"}]
		)
		waiting = make_sign_up(
			function.name, self.people[1], attendees=[{"person": self.people[1], "selection": "Adult"}]
		)
		live = make_function("_Test Waitlist Live", allow_sign_ups=1)
		kept = make_sign_up(live.name, self.people[2], attendees=[{"person": self.people[2]}])
		frappe.db.set_value(SIGN_UP, held.name, "hold_expires_on", add_to_date(now_datetime(), minutes=-5))

		with patch.object(frappe.db, "commit"):
			release_expired_holds()

		self.assertEqual(
			[status_of(held), status_of(waiting), status_of(kept)], [CANCELLED, PENDING, CONFIRMED]
		)

	def test_the_cron_keeps_a_sign_up_that_waits_for_approval(self):
		function = self.make_function(sign_up_requires_approval=1)
		waiting = make_sign_up(function.name, self.people[0], attendees=[{"person": self.people[0]}])

		with patch.object(frappe.db, "commit"):
			release_expired_holds()

		self.assertEqual(status_of(waiting), PENDING)

	def test_a_raised_capacity_promotes_the_waitlist(self):
		function = self.make_function(capacity=1)
		self.party(function.name, self.people[0])
		waiting = self.party(function.name, self.people[1])

		function.reload()
		function.capacity = 2
		with patch("frappe.enqueue", side_effect=run_promotion_now) as enqueue:
			function.save(ignore_permissions=True)
		self.assertIn(
			call(PROMOTE, function=function.name, enqueue_after_commit=True), enqueue.call_args_list
		)
		self.assertEqual(status_of(waiting), CONFIRMED)

	def test_a_waiting_party_cannot_move_itself_up(self):
		function = self.make_function(capacity=1)
		self.party(function.name, self.people[0])
		waiting = self.party(function.name, self.people[1])

		waiting.notes = "Please let me in"
		waiting.append("attendees", {"person": self.people[2]})
		waiting.save(ignore_permissions=True)
		self.assertEqual(status_of(waiting), WAITLISTED)

	def test_a_member_cancelling_promotes_the_next_party_unchanged(self):
		function = self.make_function(capacity=1)
		user = ensure_user("_test_waiting_member@example.com", "Member")
		member = make_person("_Test Waiting", "Member", user=user).name
		frappe.set_user(user)
		mine = frappe.get_doc({"doctype": SIGN_UP, "function": function.name}).insert()
		frappe.set_user("Administrator")
		waiting = self.party(function.name, self.people[0])

		frappe.set_user(user)
		frappe.get_doc(SIGN_UP, mine.name).cancel_registration()
		frappe.set_user("Administrator")

		waiting.reload()
		self.assertEqual((waiting.status, waiting.person), (CONFIRMED, self.people[0]))
		self.assertEqual(mine.person, member)
