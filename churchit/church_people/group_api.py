# Copyright (c) 2026, meichthys and contributors
# License: MIT.

import frappe
from frappe import _


def _session_person():
	"""Return the Person doc-name linked to the current session user, or None."""
	user = frappe.session.user
	if not user or user == "Guest":
		return None
	return frappe.db.get_value("Person", {"user": user}, "name")


@frappe.whitelist()
def joinable_public_groups():
	"""Return the public, portal-visible groups the current user
	isn't already a member of."""
	person = _session_person()
	mine = (
		{r.parent for r in frappe.get_all("Group Member", {"person": person, "parenttype": "Group"}, ["parent"])}
		if person else set()
	)
	rows = frappe.get_all(
		"Group",
		filters={"public": 1, "show_in_portal": 1},
		fields=["name", "group_name", "description"],
		order_by="group_name",
	)
	return [r for r in rows if r.name not in mine]


@frappe.whitelist()
def join_group(group):
	"""Add the current session user's linked Person to a public group.
	The group must have ``public = 1`` and ``show_in_portal = 1``; the
	user must already have a linked Person record."""
	if not group:
		frappe.throw(_("Group is required."))

	row = frappe.db.get_value(
		"Group", group, ["public", "show_in_portal", "group_name"], as_dict=True
	)
	if not row:
		frappe.throw(_("Group not found."))
	if not row.show_in_portal:
		frappe.throw(_("This group is not available on the portal."))
	if not row.public:
		frappe.throw(_("This group is not public — ask the group leader to add you."))

	person = _session_person()
	if not person:
		frappe.throw(
			_(
				"Your user account isn't linked to a Person record yet. "
				"Ask a church administrator to link you."
			)
		)

	if frappe.db.exists("Group Member", {"parent": group, "person": person}):
		return {"already_member": True, "group_name": row.group_name}

	member_role = frappe.db.get_value("Group Role", {"role": "Member"}, "name")
	doc = frappe.get_doc("Group", group)
	doc.append("members", {"person": person, "group_role": member_role})
	doc.save(ignore_permissions=True)
	return {"joined": True, "group_name": row.group_name}
