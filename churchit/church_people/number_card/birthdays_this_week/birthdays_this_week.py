import frappe
from frappe.query_builder.functions import Count

from churchit.query import CurDate, Month, Week


@frappe.whitelist()
def get_count():
	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")

	return (
		frappe.qb.from_(Person)
		.join(LifeEvent)
		.on(
			(LifeEvent.parent == Person.name)
			& (LifeEvent.parenttype == "Person")
			& (LifeEvent.event_type == "Birth")
		)
		.select(Count("*"))
		.where(
			LifeEvent.date.isnotnull()
			& (Week(LifeEvent.date, 1) == Week(CurDate(), 1))
			& (Month(LifeEvent.date) == Month(CurDate()))
		)
		.run()[0][0]
	)
