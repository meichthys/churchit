# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document
from frappe.utils import cint

# Check fieldname on Church Features -> the churchit module it switches.
MODULE_FIELDS = {
	"enable_people": "Church People",
	"enable_foundations": "Church Foundations",
	"enable_ministries": "Church Ministries",
	"enable_prayers": "Church Prayers",
	"enable_study": "Church Study",
	"enable_communications": "Church Communications",
	"enable_missions": "Church Missions",
	"enable_operations": "Church Operations",
	"enable_finances": "Church Finances",
	"enable_website": "Church Website",
	"enable_setup": "Church Setup",
	"enable_customizations": "Church Customizations",
}

# Kept visible whatever "Setup" is set to: the Settings workspace is where this
# page lives, so hiding it would lock the toggles away with no way back.
PROTECTED = ("Settings",)


class ChurchFeatures(Document):
	def on_update(self):
		self.apply()

	def apply(self):
		"""Hide the desk surfaces of every disabled module, restore the enabled ones.

		Nothing is deleted and no permission changes: this only flips the
		visibility flags Frappe already honours.
		"""
		disabled = self.get_disabled_modules()
		managed = self.get_managed_records()

		managed["workspaces"] = self.sync_workspaces(disabled, managed.get("workspaces") or [])
		managed["desktop_icons"] = self.sync_desktop_icons(disabled, managed.get("desktop_icons") or [])
		self.sync_blocked_modules(disabled)

		self.db_set("managed_records", json.dumps(managed, indent=1), update_modified=False)
		frappe.clear_cache()

	def get_disabled_modules(self):
		"""Return the modules whose box is explicitly unchecked.

		A field that was never written counts as enabled. That covers the Single
		nobody has saved yet, and a module added by a later churchit release:
		neither should hide itself just because it has no stored value.
		"""
		return {
			module
			for field, module in MODULE_FIELDS.items()
			if self.get(field) is not None and not cint(self.get(field))
		}

	def get_managed_records(self):
		"""Return the records this page hid on an earlier save.

		Only these are ever un-hidden again, so workspaces that churchit ships
		hidden (the Customizations ones) stay hidden when their module is on.
		"""
		if not self.managed_records:
			return {}
		try:
			return json.loads(self.managed_records)
		except ValueError:
			# Corrupt bookkeeping should not block the toggles; start over.
			return {}

	def sync_workspaces(self, disabled_modules, previously_hidden):
		"""Set is_hidden on the disabled modules' workspaces.

		Hidden public workspaces drop out of get_workspaces() for everyone
		except Workspace Managers, which in turn empties their sidebar.
		"""
		should_hide = set()
		if disabled_modules:
			should_hide = {
				name
				for name in frappe.get_all(
					"Workspace", filters={"module": ("in", sorted(disabled_modules))}, pluck="name"
				)
				if name not in PROTECTED
			}

		return self.set_flag("Workspace", "is_hidden", should_hide, previously_hidden)

	def sync_desktop_icons(self, disabled_modules, previously_hidden):
		"""Hide the app-switcher icons of the disabled modules.

		A module's sidebar survives its workspaces being hidden, because the
		sidebar also carries doctype links the user can still read. The icon is
		the only way into that sidebar, so it has to be hidden explicitly.
		"""
		should_hide = set()
		if disabled_modules:
			sidebars = [
				name
				for name in frappe.get_all(
					"Workspace Sidebar",
					filters={"module": ("in", sorted(disabled_modules)), "for_user": ("is", "not set")},
					pluck="name",
				)
				if name not in PROTECTED
			]
			if sidebars:
				should_hide = set(
					frappe.get_all(
						"Desktop Icon",
						filters={"link_type": "Workspace Sidebar", "link_to": ("in", sidebars)},
						pluck="name",
					)
				)

		return self.set_flag("Desktop Icon", "hidden", should_hide, previously_hidden)

	def set_flag(self, doctype, fieldname, should_hide, previously_hidden):
		"""Hide `should_hide`, reveal what we hid before and no longer need to.

		Returns the records this page is now responsible for. A record that was
		already hidden before we touched it never enters that set, so churchit's
		own always-hidden workspaces are not revealed when their module is on.
		"""
		previously_hidden = set(previously_hidden)
		managed = previously_hidden & should_hide

		for name in should_hide:
			if not cint(frappe.db.get_value(doctype, name, fieldname)):
				frappe.db.set_value(doctype, name, fieldname, 1)
				managed.add(name)

		for name in previously_hidden - should_hide:
			if frappe.db.exists(doctype, name):
				frappe.db.set_value(doctype, name, fieldname, 0)

		return sorted(managed)

	def sync_blocked_modules(self, disabled_modules):
		"""Mirror the disabled modules onto the Administrator's blocked modules.

		Frappe reads the Administrator's blocked modules as a site-wide block in
		frappe.utils.modules.get_modules_from_all_apps_for_user, which is what
		keeps a disabled module's dashboards, charts and number cards off the desk.
		"""
		ours = set(MODULE_FIELDS.values())
		administrator = frappe.get_doc("User", "Administrator")

		wanted = sorted(disabled_modules)
		current = sorted(row.module for row in administrator.block_modules if row.module in ours)
		if current == wanted:
			return

		administrator.block_modules = [row for row in administrator.block_modules if row.module not in ours]
		for module in wanted:
			administrator.append("block_modules", {"module": module})

		administrator.flags.ignore_permissions = True
		administrator.save()


def apply_on_migrate():
	"""after_migrate hook: put the church's choices back.

	Workspaces and Desktop Icons ship as standard records, so migrate re-imports
	them whenever churchit changes their JSON, resetting the visibility flags
	this page set.
	"""
	if not frappe.db.exists("DocType", "Church Features"):
		return

	frappe.get_single("Church Features").apply()
