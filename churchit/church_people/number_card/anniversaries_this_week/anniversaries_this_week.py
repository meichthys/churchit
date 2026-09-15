import frappe
from frappe.query_builder.functions import Count

from churchit.query import falls_this_week


@frappe.whitelist()
def get_count():
	Person = frappe.qb.DocType("Person")

	return (
		frappe.qb.from_(Person)
		.select(Count("*"))
		.where(
			Person.anniversary.isnotnull()
			& falls_this_week(Person.anniversary)
			& (Person.is_head_of_household == 1)
		)
		.run()[0][0]
	)
