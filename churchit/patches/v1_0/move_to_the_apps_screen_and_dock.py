"""Move a site onto Frappe's Apps screen, with the Churchit dock and module sidebars it ships.

Frappe's upgrade turned the old sidebars into copies owned by the site, because Churchit did not
ship sidebars in the new format yet. The ones Churchit replaces go: the merged Church Setup
sidebar, a custom "Manual: <module>" module and sidebar for each manual, a Tools module made from
the Tools workspace Churchit no longer ships, and every Churchit dock layer arranged over those.
Church Features writes the site's dock again after migrate. Desk users open Summary after login
rather than the Apps screen.
"""

import json

import frappe

from churchit.church_summary.home import land_desk_users_on_summary


def execute():
	frappe.db.set_single_value("Desktop Settings", "desktop_page", "Apps")

	churchit_modules = frappe.get_all("Module Def", filters={"app_name": "churchit"}, pluck="name")
	for name in frappe.get_all(
		"Sidebar",
		filters={"module": ("in", churchit_modules), "standard": 0, "merged_from": ("is", "set")},
		pluck="name",
	):
		frappe.delete_doc("Sidebar", name, ignore_permissions=True, force=True)

	for module in frappe.get_all(
		"Module Def",
		filters={"custom": 1, "app_name": "churchit", "name": ("like", "Manual: %")},
		pluck="name",
	):
		delete_module(module)

	tools = frappe.db.get_value("Sidebar", {"name": "Tools", "module": "Tools", "standard": 0}, "merged_from")
	if tools and json.loads(tools) == ["Tools"] and frappe.db.get_value("Module Def", "Tools", "custom"):
		delete_module("Tools")

	for name in frappe.get_all("Dock", filters={"app": "churchit", "standard": 0}, pluck="name"):
		frappe.delete_doc("Dock", name, ignore_permissions=True, force=True)

	# Church Features no longer blocks disabled modules on Administrator, which Frappe stopped
	# reading as a site-wide block.
	frappe.db.delete(
		"Block Module",
		{"parenttype": "User", "parent": "Administrator", "module": ("in", churchit_modules)},
	)

	frappe.delete_doc("Custom HTML Block", "WorkspaceHeader", ignore_missing=True, force=True)
	land_desk_users_on_summary()
	frappe.clear_cache()


def delete_module(module):
	"""Delete a custom module the upgrade made, with the users and profiles it was blocked for."""
	frappe.db.delete("Block Module", {"module": module})
	frappe.delete_doc("Module Def", module, ignore_permissions=True, force=True)
