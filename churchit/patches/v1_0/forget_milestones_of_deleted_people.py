# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Delete the membership history of people who were deleted, before a new person is given their number."""

import frappe


def execute():
	Milestone = frappe.qb.DocType("Milestone")
	Person = frappe.qb.DocType("Person")
	people = frappe.qb.from_(Person).select(Person.name)
	frappe.qb.from_(Milestone).delete().where(
		(Milestone.reference_type == "Person") & Milestone.reference_name.notin(people)
	).run()
