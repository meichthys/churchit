# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Check-In Station's Team tab: the people who serve at a Function, checked in as volunteers."""

import frappe

from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import ACCEPTED


@frappe.whitelist()
def get_team(function: str) -> list[dict]:
	"""The people with an Accepted assignment at *function*, their position, and whether they are checked in."""
	frappe.has_permission("Function Check-In", "create", throw=True)
	frappe.has_permission("Function", doc=function, throw=True)
	# church-scope: keyed to one Function the caller may read; Church Check-In has no DocPerm on assignments
	team = frappe.get_all(
		"Ministry Team Assignment",
		filters={"function": function, "status": ACCEPTED},
		fields=["person", "person_name", "position.title as position"],
		order_by="person_name asc",
	)
	if not team:
		return team

	# church-scope: the roster of the same Function
	checked_in = set(
		frappe.get_all(
			"Function Check-In",
			filters={"function": function, "person": ("in", [row.person for row in team])},
			pluck="person",
		)
	)
	for row in team:
		row.is_checked_in = row.person in checked_in
	return team


def get_position(person: str, function: str) -> str | None:
	"""The title of each position *person* accepted at *function*, for their volunteer name tag."""
	# church-scope: the check-in being printed names both, and the caller may read it
	rows = frappe.get_all(
		"Ministry Team Assignment",
		filters={"function": function, "person": person, "status": ACCEPTED},
		fields=["position.title as title"],
		order_by="creation asc",
	)
	return ", ".join(row.title for row in rows) or None
