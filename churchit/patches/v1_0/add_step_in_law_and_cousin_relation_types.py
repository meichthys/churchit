# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Add the relation types the starter list left out to existing sites.

Each is the reverse of a type sites already have (Stepfather, Father-in-law), or Cousin.
A type the church already made under the same name is left alone.
"""

import frappe

RELATION_TYPES = ("Stepson", "Stepdaughter", "Son-in-law", "Daughter-in-law", "Cousin")


def execute():
	for relation_type in RELATION_TYPES:
		if not frappe.db.exists("Person Relation Type", relation_type):
			frappe.get_doc({"doctype": "Person Relation Type", "type": relation_type}).insert(
				ignore_permissions=True
			)
