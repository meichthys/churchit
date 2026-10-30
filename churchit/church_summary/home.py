# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

SUMMARY = "Summary"


def get_summary_roles() -> list[str]:
	"""The roles Summary is for. A desk user without one, such as an ERPNext accountant, cannot open it."""
	return frappe.get_all("Has Role", filters={"parenttype": "Workspace", "parent": SUMMARY}, pluck="role")


def land_on_summary(user, method=None):
	"""validate on User: open Summary after login instead of the Apps screen.

	Set only when someone becomes a desk user who may open Summary, so a user who
	later picks another default workspace, or clears it, keeps that choice.
	"""
	if user.user_type != "System User" or user.default_workspace:
		return
	if not set(get_summary_roles()) & {row.role for row in user.roles}:
		return
	if user.is_new() or user.has_value_changed("user_type"):
		user.default_workspace = SUMMARY


def land_desk_users_on_summary():
	"""Give every desk user who may open Summary, and has no default workspace, Summary."""
	User, HasRole = frappe.qb.DocType("User"), frappe.qb.DocType("Has Role")
	may_open = (
		frappe.qb.from_(HasRole)
		.select(HasRole.parent)
		.where((HasRole.parenttype == "User") & HasRole.role.isin(get_summary_roles()))
	)
	(
		frappe.qb.update(User)
		.set(User.default_workspace, SUMMARY)
		.where(
			(User.user_type == "System User")
			& ((User.default_workspace.isnull()) | (User.default_workspace == ""))
			& User.name.isin(may_open)
		)
	).run()
