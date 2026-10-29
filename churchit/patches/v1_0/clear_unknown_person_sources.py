# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Blank the Source of the people who existed before Source was recorded.

Adding the column gave each of them its default, Desk, which nobody knows to be true.
"""

import frappe


def execute():
	Person = frappe.qb.DocType("Person")
	frappe.qb.update(Person).set(Person.source, None).run()
