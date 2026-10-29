# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give each sign-up with Attending ticked an attendee row for its person, the row that now holds a seat."""

import frappe


def execute():
	SignUp = frappe.qb.DocType("Function Sign-Up")
	Attendee = frappe.qb.DocType("Function Sign-Up Attendee")
	Person = frappe.qb.DocType("Person")
	listed = (
		frappe.qb.from_(Attendee).select(Attendee.parent).where(Attendee.parenttype == "Function Sign-Up")
	)
	sign_ups = (
		frappe.qb.from_(SignUp)
		.join(Person)
		.on(Person.name == SignUp.person)
		.select(SignUp.name, SignUp.person, Person.full_name)
		.where((SignUp.attending == 1) & SignUp.name.notin(listed))
		.run()
	)
	for name, person, full_name in sign_ups:
		frappe.get_doc(
			{
				"doctype": "Function Sign-Up Attendee",
				"parent": name,
				"parenttype": "Function Sign-Up",
				"parentfield": "attendees",
				"person": person,
				"attendee_name": full_name,
				"idx": 1,
			}
		).db_insert()
