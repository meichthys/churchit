import frappe
from frappe.query_builder.functions import Count

from churchit.church_scope import scoped
from churchit.query import falls_this_week


@frappe.whitelist()
def get_count():
	frappe.has_permission("Person", "report", throw=True)
	Person = frappe.qb.DocType("Person")

	query = (
		frappe.qb.from_(Person)
		.select(Count("*"))
		.where(
			Person.anniversary.isnotnull()
			& falls_this_week(Person.anniversary)
			& (Person.is_head_of_household == 1)
		)
	)
	return scoped(query, Person, {}).run()[0][0]
