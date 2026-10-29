# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Background Checks a Group needs of its leaders or members."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from churchit.church_people.doctype.background_check.background_check import get_check_problem
from churchit.church_people.group_leaders import get_leader_roles


def check_member_requirements(group: Document) -> None:
	"""Refuse, or warn about, new or role-changed members of *group* who lack its required checks."""
	if not group.needs_background_check:
		return

	required = [row.check_type for row in group.required_checks]
	problems = [
		problem
		for row in get_rows_to_check(group)
		if (problem := get_check_problem(row.person, getdate(), required, group.group_name))
	]
	if not problems:
		return

	if group.block_without_checks:
		frappe.throw(problems, title=_("Not cleared to serve"), as_list=True)
	frappe.msgprint(problems, title=_("Check these members"), indicator="orange", as_list=True)


def get_rows_to_check(group: Document) -> list[Document]:
	"""The member rows that are new or in a new role since the last save, and that the group's rule covers."""
	before = group.get_doc_before_save()
	saved = {(row.person, row.group_role) for row in before.members} if before else set()
	rows = [row for row in group.members if (row.person, row.group_role) not in saved]
	if group.checks_apply_to == "Everyone":
		return rows

	leader_roles = set(get_leader_roles())
	return [row for row in rows if row.group_role in leader_roles]
