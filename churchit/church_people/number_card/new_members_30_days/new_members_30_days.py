import frappe

from churchit.church_people.report.new_members_last_90_days.new_members_last_90_days import new_members_query
from churchit.church_scope import scoped


@frappe.whitelist(methods=["GET", "POST"])
def get_count() -> dict:
	"""Number card: the new members that the New Members report lists for 30 days, in the caller's churches. Reads only."""
	frappe.has_permission("Person", "report", throw=True)
	Person = frappe.qb.DocType("Person")
	new_members = scoped(new_members_query(Person, 30), Person, {}).run()
	return {
		"value": len(new_members),
		"fieldtype": "Int",
		"route": ["query-report", "New Members Last 90 Days"],
		"route_options": {"days": 30},
	}
