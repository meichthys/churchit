# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fill the digits of every phone number saved before Phone Number kept them."""

import frappe

from churchit.contacts import PHONE_DOCTYPE, phone_digits


def execute():
	rows = frappe.get_all(
		PHONE_DOCTYPE, filters={"digits": ("is", "not set")}, fields=["name", "phone_number"]
	)
	for row in rows:
		digits = phone_digits(row.phone_number)
		if digits:
			frappe.db.set_value(PHONE_DOCTYPE, row.name, "digits", digits, update_modified=False)
