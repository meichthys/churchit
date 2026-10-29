# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Who may read a Prayer Request: its Visibility decides.

A Private request is read by its requester and by the staff roles that read every request. Church Prayer Team
reads the Prayer Team and Whole Church ones, in the desk and on the Community Prayer Requests page, where every
member reads the Whole Church ones. A bulletin prints only Whole Church requests.
"""

import frappe
from frappe.utils import now_datetime

from churchit.church_scope import church_filters, default_church, session_church

PRAYER_REQUEST = "Prayer Request"
PRAYER_TEAM_ROLE = "Church Prayer Team"
PRIVATE = "Private"
PRAYER_TEAM = "Prayer Team"
WHOLE_CHURCH = "Whole Church"
CLOSED_STATUSES = ("Answered", "Archived", "Closed")


def has_prayer_permission(doc, ptype=None, user=None) -> bool:
	"""has_permission hook: the prayer team's right never opens another person's Private request.

	Frappe reads any falsy return as a refusal, so every other user gets True.
	"""
	user = user or frappe.session.user
	if doc.visibility != PRIVATE or not is_prayer_team_only(user):
		return True
	return doc.owner == user


def prayer_query_conditions(user=None, doctype=None) -> str:
	"""permission_query_conditions hook: the prayer team lists no Private request but its own."""
	user = user or frappe.session.user
	if not is_prayer_team_only(user):
		return ""
	return (
		f"(`tabPrayer Request`.`visibility` != {frappe.db.escape(PRIVATE)}"
		f" or `tabPrayer Request`.`owner` = {frappe.db.escape(user)})"
	)


def is_prayer_team_only(user: str) -> bool:
	"""True when *user* reads other people's requests only through the Church Prayer Team role."""
	readers = {
		perm.role
		for perm in frappe.get_meta(PRAYER_REQUEST).permissions
		if perm.read and not perm.if_owner and not perm.permlevel
	}
	return readers & set(frappe.get_roles(user)) == {PRAYER_TEAM_ROLE}


def get_community_filters() -> dict:
	"""Filters for the requests the Community Prayer Requests page shows the signed-in member.

	The page reads past document permissions, so it applies the member's church and the visibilities here.
	"""
	visibilities = [WHOLE_CHURCH]
	if PRAYER_TEAM_ROLE in frappe.get_roles():
		visibilities.append(PRAYER_TEAM)
	return church_filters(session_church() or default_church(), visibility=("in", visibilities))


def get_open_request_filters() -> tuple[dict, list]:
	"""`(filters, or_filters)` for the requests a list shows: open, approved for the list and not ended.

	They apply no church or visibility, so the caller adds those.
	"""
	filters = {"status": ("not in", CLOSED_STATUSES), "approved_for_list": ("=", 1)}
	or_filters = [["end_date", "is", "not set"], ["end_date", ">=", now_datetime()]]
	return filters, or_filters
