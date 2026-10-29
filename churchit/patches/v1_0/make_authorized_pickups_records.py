# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give each Authorized Pickup its family and the family's church.

An Authorized Pickup was a row of the Family's table, which every church's check-in volunteers could
list. It is now a record of its own, scoped to the family's church. A row keeps the `parent` column it
had as a table row, so the family comes from there.
"""

import frappe

PICKUP = "Authorized Pickup"


def execute():
	if not frappe.db.has_column(PICKUP, "parent"):
		return
	frappe.db.sql(
		"""
		update `tabAuthorized Pickup` pickup
		join `tabFamily` family on family.name = pickup.parent
		set pickup.family = family.name, pickup.church = family.church
		where pickup.parenttype = 'Family' and pickup.family is null
		"""
	)
