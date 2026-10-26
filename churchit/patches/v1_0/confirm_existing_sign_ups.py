# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give each sign-up made before sign-ups had a status the status Confirmed, which it held then."""

import frappe


def execute():
	# A direct update: a save would refuse a sign-up of a closed function and send confirmation emails.
	frappe.db.set_value(
		"Function Sign-Up", {"status": ("is", "not set")}, "status", "Confirmed", update_modified=False
	)
