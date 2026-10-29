# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Rename Care Request's Assigned To (a Person) to Caregiver.

Frappe's assign_to writes the assignee's User ID into any field named `assigned_to`, and
clears it when the assignment is removed, so assigning a request from the sidebar put a
User ID in a Person link. A value that names no Person is such a User ID: it becomes that
user's Person, or is cleared when no Person has that login.

Runs post_model_sync, so the caregiver column exists. A second run finds caregivers
already set and leaves them alone.
"""

import frappe
from frappe.model.utils.rename_field import rename_field

DOCTYPE = "Care Request"
OLD = "assigned_to"
NEW = "caregiver"


def execute():
	if not frappe.db.has_column(DOCTYPE, OLD) or frappe.db.exists(DOCTYPE, {NEW: ("is", "set")}):
		return
	rename_field(DOCTYPE, OLD, NEW)
	repair_user_ids()


def repair_user_ids():
	Request = frappe.qb.DocType(DOCTYPE)
	Person = frappe.qb.DocType("Person")
	strays = (
		frappe.qb.from_(Request)
		.left_join(Person)
		.on(Person.name == Request.caregiver)
		.select(Request.name, Request.caregiver)
		.where(Request.caregiver.isnotnull() & (Request.caregiver != "") & Person.name.isnull())
		.run(as_dict=True)
	)
	for stray in strays:
		person = frappe.db.get_value("Person", {"user": stray.caregiver})
		frappe.db.set_value(DOCTYPE, stray.name, NEW, person, update_modified=False)
