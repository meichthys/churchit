# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

SUMMARY = "Summary"


def land_on_summary(user, method=None):
	"""validate on User: open Summary after login instead of the Apps screen.

	Set only when someone becomes a desk user, so a user who later picks
	another default workspace, or clears it, keeps that choice.
	"""
	if user.user_type != "System User" or user.default_workspace:
		return
	if user.is_new() or user.has_value_changed("user_type"):
		user.default_workspace = SUMMARY


def land_desk_users_on_summary():
	"""Give every desk user without a default workspace Summary."""
	User = frappe.qb.DocType("User")
	(
		frappe.qb.update(User)
		.set(User.default_workspace, SUMMARY)
		.where(
			(User.user_type == "System User")
			& ((User.default_workspace.isnull()) | (User.default_workspace == ""))
		)
	).run()
