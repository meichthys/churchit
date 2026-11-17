# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Which number cards a user sees: a card that counts every prayer or care request needs a role that reads them all.

Church Staff, and the profiles built on it, read only the prayer and care requests they made. Frappe shows a
card to anyone with any read on its doctype, so without this they saw counts that always read zero.
"""

import frappe

# The whole-church queues that only the care roles read in full.
QUEUES = ("Prayer Request", "Care Request")


def has_card_permission(doc, ptype=None, user=None) -> bool:
	"""has_permission hook on Number Card: refuse a queue's card to a user who reads only their own requests.

	Frappe reads any falsy return as a refusal, so every other card gets True.
	"""
	return doc.document_type not in get_own_only_queues(user or frappe.session.user)


def card_query_conditions(user=None, doctype=None) -> str:
	"""permission_query_conditions hook on Number Card: leave out the same cards from a list."""
	queues = get_own_only_queues(user or frappe.session.user)
	if not queues:
		return ""
	names = ", ".join(frappe.db.escape(queue) for queue in queues)
	return f"ifnull(`tabNumber Card`.`document_type`, '') not in ({names})"


def get_own_only_queues(user: str) -> list[str]:
	"""The queues that *user* reads only as the owner of a request."""
	roles = set(frappe.get_roles(user))
	return [queue for queue in QUEUES if reads_only_own(queue, roles)]


def reads_only_own(doctype: str, roles: set[str]) -> bool:
	"""True when every read of *doctype* that *roles* hold is limited to the records they made."""
	reads = [
		perm
		for perm in frappe.get_meta(doctype).permissions
		if perm.read and not perm.permlevel and perm.role in roles
	]
	return bool(reads) and all(perm.if_owner for perm in reads)
