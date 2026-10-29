import frappe
from frappe.query_builder.functions import Count

from churchit.church_people.membership import living_people_filter
from churchit.church_scope import scoped
from churchit.query import month_day_this_week


@frappe.whitelist()
def get_count():
	frappe.has_permission("Person", "report", throw=True)
	Person = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(Person)
		.select(Count("*"))
		.where(month_day_this_week(Person.birth_month, Person.birth_day))
		.where(living_people_filter(Person))
	)
	return scoped(query, Person, {}).run()[0][0]
