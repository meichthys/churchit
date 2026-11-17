# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Hide the dock entries a desk user cannot use, in the user's own Dock layer.

An entry is empty for a user when the user opens no workspace of its module and reads no
Churchit page of its sidebar. Frappe still shows such an entry when the user reads one Frappe
page of it, such as Email Templates. The state is owned here: the entries this module hid are
kept in a user default, so only those are shown again when a role gives the user a page.
Church Features owns the entries of a module that is switched off and calls `sync_user_dock`
for every layer, so a switched-off module is never shown again from here.
"""

import json

import frappe
from frappe.desk.doctype.dock.dock import get_app_dock, resolve_app_dock
from frappe.utils import cint

APP = "churchit"
DEFAULT_KEY = "churchit_empty_dock_entries"


def get_empty_sidebars(user: str) -> set[str]:
	"""Return the sidebars of the Churchit dock that the user cannot open anything in."""
	roles = set(frappe.get_roles(user))
	if "Workspace Manager" in roles:
		return set()

	churchit_modules = frappe.get_all("Module Def", filters={"app_name": APP}, pluck="name")
	empty = set()
	for entry in get_app_dock(APP):
		if entry["link_type"] != "Sidebar":
			continue
		sidebar = frappe.get_cached_doc("Sidebar", entry["link_to"])
		if not (
			has_workspace(sidebar.module, roles) or has_readable_page(sidebar, user, roles, churchit_modules)
		):
			empty.add(entry["link_to"])

	return empty


def has_workspace(module: str, roles: set[str]) -> bool:
	"""Return whether the roles open a visible workspace of the module."""
	for name in frappe.get_all(
		"Workspace", filters={"module": module, "public": 1, "is_hidden": 0}, pluck="name"
	):
		allowed = frappe.get_all(
			"Has Role", filters={"parenttype": "Workspace", "parent": name}, pluck="role"
		)
		if not allowed or roles & set(allowed):
			return True

	return False


def has_readable_page(sidebar, user: str, roles: set[str], churchit_modules: list[str]) -> bool:
	"""Return whether the user reads a list, report or page of Churchit that the sidebar links."""
	for item in sidebar.items:
		if item.type == "Link" and is_readable(item.link_type, item.link_to, user, roles, churchit_modules):
			return True

	return False


def is_readable(
	link_type: str, link_to: str, user: str, roles: set[str], churchit_modules: list[str]
) -> bool:
	if link_type not in ("DocType", "Report", "Page") or not link_to:
		return False

	if frappe.db.get_value(link_type, link_to, "module") not in churchit_modules:
		return False

	if link_type == "DocType":
		return frappe.has_permission(link_to, "read", user=user)

	if link_type == "Page":
		return frappe.has_permission("Page", "read", link_to, user=user)

	allowed = frappe.get_all("Has Role", filters={"parenttype": "Report", "parent": link_to}, pluck="role")
	ref_doctype = frappe.db.get_value("Report", link_to, "ref_doctype")
	return (not allowed or bool(roles & set(allowed))) and frappe.has_permission(
		ref_doctype, "read", user=user
	)


def get_hidden_by_us(user: str) -> set[str]:
	return set(json.loads(frappe.defaults.get_user_default(DEFAULT_KEY, user) or "[]"))


def sync_user_dock(user: str, hide: set[str] | None = None, reveal: set[str] | None = None) -> None:
	"""Lay the module switches (`hide`, `reveal`) and the user's empty entries over the user's layer.

	Without a layer, one is made only when something must be hidden. A layer is the whole rail, so
	it starts from the site's arrangement. A layer the user arranged keeps the entries it names.
	"""
	if hide is None:
		hide = get_disabled_sidebars()

	empty = get_empty_sidebars(user)
	previous = get_hidden_by_us(user)
	reveal = ((reveal or set()) | previous) - empty - hide

	name = frappe.db.get_value("Dock", {"app": APP, "standard": 0, "user": user})
	if not name and not empty:
		return

	dock = frappe.get_doc("Dock", name) if name else new_user_dock(user)
	set_dock_flags(dock, hide | empty, reveal, save=dock.is_new())
	frappe.defaults.set_user_default(DEFAULT_KEY, json.dumps(sorted(empty)), user)


def new_user_dock(user: str):
	"""Return an unsaved layer that holds the site's arrangement, hidden flags included."""
	dock = frappe.get_doc({"doctype": "Dock", "app": APP, "user": user})
	for entry in resolve_app_dock(APP, upto="site", gated=False):
		dock.append(
			"items",
			{"link_type": entry["link_type"], "link_to": entry["link_to"], "hidden": entry["hidden"]},
		)

	return dock


def get_sidebars_of_modules(modules) -> set[str]:
	if not modules:
		return set()

	return set(frappe.get_all("Sidebar", filters={"module": ("in", sorted(modules))}, pluck="name"))


def get_disabled_sidebars() -> set[str]:
	"""Return the sidebars Church Features hides."""
	return get_sidebars_of_modules(frappe.get_single("Church Features").get_disabled_modules())


def sync_user_on_roles_change(user, method=None) -> None:
	"""on_update on User: re-check the dock entries after a role or role profile change."""
	if user.user_type == "System User" and user.name not in ("Administrator", "Guest"):
		sync_user_dock(user.name)


def sync_every_user() -> None:
	"""Lay the empty entries over the dock of every enabled desk user."""
	for name in frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User", "name": ("not in", ("Administrator", "Guest"))},
		pluck="name",
	):
		sync_user_dock(name)


def set_dock_flags(dock, hide, reveal, save=False):
	"""Hide the `hide` sidebars on one dock layer and show the `reveal` ones. Returns the entries it hid."""
	hidden = set()
	for row in dock.items:
		wanted = 1 if row.link_to in hide else 0 if row.link_to in reveal else cint(row.hidden)
		if row.link_type != "Sidebar" or wanted == cint(row.hidden):
			continue
		row.hidden = wanted
		save = True
		if wanted:
			hidden.add(row.link_to)

	if save:
		dock.save(ignore_permissions=True)
	return hidden
