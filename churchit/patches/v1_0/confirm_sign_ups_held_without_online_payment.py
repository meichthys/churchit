# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Confirm the sign-ups held for a payment that cannot be made online.

A church with no payment gateway confirms a priced sign-up and keeps it Unpaid. Holds that began before
this rule would still expire and cancel. A sign-up that waits for approval keeps waiting.
"""

import frappe
from frappe.utils import flt

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import CONFIRMED, PENDING, UNPAID


def execute():
	# church-scope: a patch over every church; each sign-up follows its own payment church
	held = frappe.get_all(
		"Function Sign-Up",
		filters={"status": PENDING, "hold_expires_on": ("is", "set")},
		fields=["name", "approved_by", "amount_due", "amount_paid", "payment_status"],
	)
	for row in held:
		sign_up = frappe.get_doc("Function Sign-Up", row.name)
		if sign_up.has_online_payment or not is_released_from_approval(sign_up):
			continue

		values = {"status": CONFIRMED, "hold_expires_on": None}
		if not row.payment_status and flt(row.amount_due) > flt(row.amount_paid):
			values["payment_status"] = UNPAID
		# A direct update: a save would send confirmation emails.
		frappe.db.set_value("Function Sign-Up", row.name, values, update_modified=False)


def is_released_from_approval(sign_up) -> bool:
	return bool(
		sign_up.approved_by
		or not frappe.db.get_value("Function", sign_up.function, "sign_up_requires_approval")
	)
