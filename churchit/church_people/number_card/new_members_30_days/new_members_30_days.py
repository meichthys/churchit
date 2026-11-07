import frappe
from frappe.query_builder.functions import Count
from frappe.utils import add_days, nowdate

from churchit.church_scope import scoped


@frappe.whitelist(methods=["GET", "POST"])
def get_count() -> int:
	"""Number card: the Membership life events of the last 30 days, in the caller's churches. Reads only."""
	frappe.has_permission("Person", "report", throw=True)
	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")
	query = (
		frappe.qb.from_(LifeEvent)
		.join(Person)
		.on((LifeEvent.parent == Person.name) & (LifeEvent.parenttype == "Person"))
		.select(Count("*"))
		.where((LifeEvent.event_type == "Membership") & (LifeEvent.date >= add_days(nowdate(), -30)))
	)
	return scoped(query, Person, {}).run()[0][0]
