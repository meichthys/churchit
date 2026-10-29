# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Checkout at the Check-In Station: when someone checked in has left.

`collected_at` is the one checkout state. A child with a pickup tag leaves through Verify Pickup
(`check_in.release_children`), which also stores who collected them. Anyone else is checked out here.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime


@frappe.whitelist(methods=["POST"])
def check_out(check_in: str) -> None:
	"""Record that the person of *check_in*, who has no pickup tag, has left."""
	frappe.get_doc("Function Check-In", check_in).check_permission("write")
	row = lock_check_in(check_in)
	if row.security_code:
		frappe.throw(
			_("This person has a pickup tag, so they leave through Verify Pickup."), frappe.PermissionError
		)
	if row.collected_at:
		frappe.throw(_("This person has already been checked out."))

	doc = frappe.get_doc("Function Check-In", check_in)
	doc.update({"collected_at": now_datetime(), "released_by": frappe.session.user})
	doc.flags.checkout = True
	doc.save()


def lock_check_in(check_in: str) -> frappe._dict:
	"""Lock *check_in*'s Function row, then the check-in row, and return the row's checkout state.

	A check-in locks the Function row first (`add_check_ins`), so this takes the locks in the same order.
	Both hold to commit, so a second volunteer waits here and then sees the first one's change.
	"""
	if function := frappe.db.get_value("Function Check-In", check_in, "function"):
		frappe.db.get_value("Function", function, "name", for_update=True)
	row = frappe.db.get_value(
		"Function Check-In", check_in, ["security_code", "collected_at"], as_dict=True, for_update=True
	)
	if not row:
		frappe.throw(
			_("{0} {1} not found").format(_("Function Check-In"), check_in), frappe.DoesNotExistError
		)
	return row
