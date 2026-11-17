# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import PropertyMock, patch

import frappe
from frappe.utils import add_to_date, now_datetime

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CANCELLED,
	CONFIRMED,
	PENDING,
	UNPAID,
	FunctionSignUp,
	release_expired_holds,
)
from churchit.church_ministries.doctype.function_sign_up.test_sign_up_seats import make_sign_up
from churchit.patches.v1_0 import confirm_sign_ups_held_without_online_payment
from churchit.tests.helpers import RollbackEachTest, make_function, make_person

SIGN_UP = "Function Sign-Up"
ADULT = {"selection": "Adult"}


def set_online_payment(is_online: bool):
	return patch.object(
		FunctionSignUp, "has_online_payment", new_callable=PropertyMock, return_value=is_online
	)


class TestConfirmHeldSignUpsPatch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.people = [make_person("_Test Held", name).name for name in ("Ann", "Ben")]

	def make_held(self, person: str, **function_values):
		"""A sign-up held for a payment, as it was before a church with no gateway confirmed such sign-ups."""
		function = make_function(
			"_Test Held Retreat",
			allow_sign_ups=1,
			selections=[{"selection": "Adult", "price": 20}],
			**function_values,
		)
		with set_online_payment(True):
			held = make_sign_up(function.name, person, attendees=[{**ADULT, "person": person}])
		self.assertEqual((held.status, bool(held.hold_expires_on)), (PENDING, True))
		return held

	def test_a_hold_that_cannot_be_paid_online_is_confirmed_unpaid_and_never_expires(self):
		held = self.make_held(self.people[0])
		frappe.db.set_value(SIGN_UP, held.name, "hold_expires_on", add_to_date(now_datetime(), hours=-1))
		queued_before = frappe.db.count("Email Queue")

		with set_online_payment(False):
			confirm_sign_ups_held_without_online_payment.execute()
			confirm_sign_ups_held_without_online_payment.execute()
			release_expired_holds()

		stored = frappe.db.get_value(SIGN_UP, held.name, ["status", "payment_status", "hold_expires_on"])
		self.assertEqual(tuple(stored), (CONFIRMED, UNPAID, None))
		self.assertEqual(frappe.db.count("Email Queue"), queued_before)

	def test_a_hold_that_can_be_paid_online_is_left_to_run(self):
		held = self.make_held(self.people[0])

		with set_online_payment(True):
			confirm_sign_ups_held_without_online_payment.execute()

		self.assertEqual(frappe.db.get_value(SIGN_UP, held.name, "status"), PENDING)

	def test_a_sign_up_that_waits_for_approval_keeps_waiting(self):
		held = self.make_held(self.people[0])
		frappe.db.set_value("Function", held.function, "sign_up_requires_approval", 1)

		with set_online_payment(False):
			confirm_sign_ups_held_without_online_payment.execute()

		self.assertEqual(frappe.db.get_value(SIGN_UP, held.name, "status"), PENDING)

	def test_a_cancelled_sign_up_stays_cancelled(self):
		held = self.make_held(self.people[0])
		frappe.db.set_value(SIGN_UP, held.name, "status", CANCELLED)

		with set_online_payment(False):
			confirm_sign_ups_held_without_online_payment.execute()

		self.assertEqual(frappe.db.get_value(SIGN_UP, held.name, "status"), CANCELLED)
