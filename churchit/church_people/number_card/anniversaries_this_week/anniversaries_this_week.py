import frappe
from frappe.query_builder.functions import Count

from churchit.query import CurDate, Month, Week


@frappe.whitelist()
def get_count():
	Person = frappe.qb.DocType("Person")

	return (
		frappe.qb.from_(Person)
		.select(Count("*"))
		.where(
			Person.anniversary.isnotnull()
			& (Week(Person.anniversary, 1) == Week(CurDate(), 1))
			& (Month(Person.anniversary) == Month(CurDate()))
			& (Person.is_head_of_household == 1)
		)
		.run()[0][0]
	)
