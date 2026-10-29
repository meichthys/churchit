# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Who leads a group: its members in a Group Role with Leads the Group ticked."""

import frappe
from frappe import _

from churchit.church_scope import session_person


def get_leaders(group: str) -> list[str]:
	"""The people who lead *group*."""
	# church-scope: the member rows of one group
	return frappe.get_all(
		"Group Member",
		filters={"parenttype": "Group", "parent": group, "group_role": ("in", get_leader_roles())},
		pluck="person",
		distinct=True,
	)


def is_group_leader(group: str, person: str | None) -> bool:
	return bool(person) and person in get_leaders(group)


def get_led_groups(person: str) -> list[str]:
	"""The groups *person* leads."""
	# church-scope: one person's member rows
	return frappe.get_all(
		"Group Member",
		filters={"parenttype": "Group", "person": person, "group_role": ("in", get_leader_roles())},
		pluck="parent",
		distinct=True,
	)


def require_leader(group: str) -> str:
	"""The session user's Person when they lead *group*. Anyone else gets PermissionError."""
	person = session_person()
	if not is_group_leader(group, person):
		frappe.throw(_("Only a leader of this group can do this."), frappe.PermissionError)
	return person


def get_leader_roles() -> list[str]:
	return frappe.get_all("Group Role", filters={"is_leader": 1}, pluck="name")
