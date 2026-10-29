import frappe
from frappe.query_builder.functions import Count

from churchit.church_people.doctype.family.family import primary_contacts
from churchit.church_people.membership import living_people_filter
from churchit.church_scope import scoped
from churchit.query import falls_this_week


@frappe.whitelist()
def get_count():
	frappe.has_permission("Person", "report", throw=True)
	Person = frappe.qb.DocType("Person")
	Spouse = frappe.qb.DocType("Person").as_("spouse")

	query = (
		frappe.qb.from_(Person)
		.left_join(Spouse)
		.on(Spouse.name == Person.spouse)
		.select(Count("*"))
		.where(
			Person.anniversary.isnotnull()
			& falls_this_week(Person.anniversary)
			& Person.name.isin(primary_contacts())
		)
		.where(living_people_filter(Person) & (Spouse.name.isnull() | living_people_filter(Spouse)))
	)
	return scoped(query, Person, {}).run()[0][0]
