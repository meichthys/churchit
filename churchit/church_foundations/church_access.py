# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Keeps each user's Church User Permission in step with their Person."""

import frappe
from frappe import _
from frappe.permissions import add_user_permission
from frappe.utils import sbool

from churchit.church_scope import EXPAND_FILTER_DEFAULT, is_multi_church

UNSCOPED_USERS = ("Administrator", "Guest")


def user_church_permissions(user):
	return frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Church"},
		fields=["name", "for_value", "hide_descendants"],
	)


def set_user_church(user, church):
	"""Point the user's Church permission at `church`, replacing any other one."""
	existing = user_church_permissions(user)
	if len(existing) == 1 and existing[0].for_value == church:
		return
	for permission in existing:
		frappe.delete_doc("User Permission", permission.name, ignore_permissions=True, force=True)
	add_user_permission("Church", church, user, ignore_permissions=True, is_default=1, hide_descendants=1)


def move_church_permissions(church, destination):
	"""Point everyone scoped to *church* at *destination* instead.

	Called when a church is deleted. A permission that outlives its church hides
	every record of every other church from the user holding it, and deleting it
	outright would do the opposite: no Church permission means no restriction, so
	they would see every church. The parent is where a closed branch's people
	belong, and it keeps them scoped either way.
	"""
	holders = frappe.get_all(
		"User Permission", filters={"allow": "Church", "for_value": church}, pluck="user"
	)
	for user in holders:
		set_user_church(user, destination)


def grant_root_permission_to_users(root):
	"""Give every enabled user without a Church permission the root church, branches hidden."""
	bound = set(frappe.get_all("User Permission", filters={"allow": "Church"}, pluck="user"))
	users = frappe.get_all("User", filters={"enabled": 1, "name": ("not in", UNSCOPED_USERS)}, pluck="name")
	for user in users:
		if user not in bound:
			add_user_permission(
				"Church", root, user, ignore_permissions=True, is_default=1, hide_descendants=1
			)


def scope_new_user(doc, method=None):
	"""after_insert on User: give a new login the church it was created in.

	A user with no Church permission is unrestricted, so a login made outside the
	Person invite (the desk User list, a website sign-up) used to see every
	church. The church the request is about is the best guess available: the
	branch whose page took a sign-up, or the church of whoever is adding the user
	in the desk. Linking a Person repoints it, so this is only the starting point.
	"""
	from churchit.church_foundations.doctype.church.church import selected_church_name

	if not is_multi_church() or doc.name in UNSCOPED_USERS or not doc.enabled:
		return
	if user_church_permissions(doc.name):
		return
	church = selected_church_name()
	if church:
		add_user_permission(
			"Church", church, doc.name, ignore_permissions=True, is_default=1, hide_descendants=1
		)


def include_branches_state(user):
	"""True or False for a user whose church has branches to include; None for everyone else."""
	if not is_multi_church() or user in UNSCOPED_USERS:
		return None
	permissions = user_church_permissions(user)
	if len(permissions) != 1 or not has_branches(permissions[0].for_value):
		return None
	return not permissions[0].hide_descendants


def has_branches(church):
	left, right = frappe.db.get_value("Church", church, ["lft", "rgt"])
	return (right or 0) - (left or 0) > 1


@frappe.whitelist()
def set_church_filter_expansion(expand: bool):
	"""Remember whether a church picked in a report filter should bring its branches along."""
	frappe.defaults.set_user_default(EXPAND_FILTER_DEFAULT, "1" if sbool(expand) else "0")
	return bool(sbool(expand))


@frappe.whitelist()
def set_include_branches(include: bool):
	"""Flip branch visibility on the caller's own Church permission."""
	user = frappe.session.user
	if include_branches_state(user) is None:
		frappe.throw(_("Your church has no branches to include."))
	permission = frappe.get_doc("User Permission", user_church_permissions(user)[0].name)
	permission.hide_descendants = 0 if sbool(include) else 1
	permission.save(ignore_permissions=True)
	return not permission.hide_descendants
