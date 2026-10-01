import frappe
from frappe.query_builder.functions import Count

from churchit.church_scope import scoped
from churchit.query import falls_this_week


@frappe.whitelist()
def get_count():
	frappe.has_permission("Person", "report", throw=True)
	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")

	query = (
		frappe.qb.from_(Person)
		.join(LifeEvent)
		.on(
			(LifeEvent.parent == Person.name)
			& (LifeEvent.parenttype == "Person")
			& (LifeEvent.event_type == "Birth")
		)
		.select(Count("*"))
		.where(LifeEvent.date.isnotnull() & falls_this_week(LifeEvent.date))
	)
	return scoped(query, Person, {}).run()[0][0]
