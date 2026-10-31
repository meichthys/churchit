# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.desk.doctype.dock.dock import dock_key, get_app_dock

SUMMARY = "Summary"
# On Framework's rail, the way back to churchit.
RETURN_ENTRY = {"link_type": "Sidebar", "link_to": SUMMARY, "icon": "church", "title": "Churchit", "added": 1}


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


def add_return_to_framework_dock():
	"""Put Churchit first on the site's arrangement of Framework's rail.

	A Frappe page that no churchit sidebar lists opens in Framework, whose rail
	otherwise leads back only through the Apps screen. A saved arrangement is the
	whole rail, so it also gets each entry Framework ships that it does not name
	yet. Runs on every migrate; a hidden entry keeps its flag.
	"""
	name = frappe.db.get_value("Dock", {"app": "frappe", "standard": 0, "user": ""})
	dock = frappe.get_doc("Dock", name) if name else frappe.get_doc({"doctype": "Dock", "app": "frappe"})
	named = {dock_key(row) for row in dock.items}
	missing = [entry for entry in get_app_dock("frappe") if dock_key(entry) not in named]
	for entry in missing:
		dock.append("items", {field: entry.get(field) for field in ("link_type", "link_to", "url")})

	if dock_key(RETURN_ENTRY) not in named:
		dock.append("items", RETURN_ENTRY)
		dock.items.insert(0, dock.items.pop())
	elif not missing:
		return

	for idx, row in enumerate(dock.items, 1):
		row.idx = idx
	dock.save(ignore_permissions=True)
