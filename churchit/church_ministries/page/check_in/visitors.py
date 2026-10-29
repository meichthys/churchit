# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Visitor matching for the Check-In Station's New Visitor dialog."""

import frappe
from frappe.utils import cstr

from churchit.church_ministries.page.check_in.check_in import get_people_scope, group_by_family
from churchit.church_people.matching import find_matches, get_clean_candidate


@frappe.whitelist()
def find_visitor_matches(
	function: str | None, first_name: str | None, last_name: str | None = None, phone: str | None = None
) -> list[dict]:
	"""People on file who may be the new visitor, grouped by family as a station search finds them.

	The matcher reads every church, so its matches pass the station's one gate, `get_people_scope`.
	A name alone scores under the match threshold, so people with the same first and last name are
	offered too: a volunteer confirms each one.
	"""
	frappe.has_permission("Function Check-In", "create", throw=True)
	scope = get_people_scope(function)
	first_name, last_name = cstr(first_name).strip(), cstr(last_name).strip()
	candidate = get_clean_candidate({"first_name": first_name, "last_name": last_name, "phones": [phone]})
	people = [match.person for match in find_matches(candidate, limit=5)]
	if first_name and last_name:
		# church-scope: *scope* is get_people_scope's answer for this station
		people += frappe.get_all(
			"Person",
			filters={"first_name": first_name, "last_name": last_name, **scope},
			pluck="name",
			limit=5,
		)
	return group_by_family(people, scope)
