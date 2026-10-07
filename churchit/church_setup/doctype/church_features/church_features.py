# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from churchit.church_foundations import church_access
from churchit.church_scope import root_church
from churchit.church_setup import multi_church

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
	def validate(self):
		if cint(self.enable_multi_church) and not root_church():
			frappe.throw(_("Create the Church record before enabling Multi-Church."))
		if self.multi_church_changed_to(False) and frappe.db.count("Church") > 1:
			frappe.throw(_("Multi-Church cannot be turned off while branch churches exist."))

	def on_update(self):
		self.apply()
		if self.multi_church_changed_to(True):
			self.start_multi_church()

	def multi_church_changed_to(self, enabled):
		before = self.get_doc_before_save()
		was_enabled = bool(cint(before and before.enable_multi_church))
		return bool(cint(self.enable_multi_church)) == enabled and was_enabled != enabled

	def apply(self):
		"""Hide the desk surfaces of every disabled module, restore the enabled ones.

		Also hides other apps' desktop icons unless Show Other Apps is ticked.
		Nothing is deleted and no permission changes: this only flips the
		visibility flags Frappe already honours.
		"""
		disabled = self.get_disabled_modules()
		managed = self.get_managed_records()

		managed["workspaces"] = self.sync_workspaces(disabled, managed.get("workspaces") or [])
		managed["desktop_icons"] = self.sync_desktop_icons(disabled, managed.get("desktop_icons") or [])
		managed["other_app_icons"] = self.sync_other_app_icons(managed.get("other_app_icons") or [])
		self.sync_blocked_modules(disabled)
		multi_church.apply_field_visibility(cint(self.enable_multi_church))
		multi_church.apply_people_privacy(cint(self.private_people))

		self.db_set("managed_records", json.dumps(managed, indent=1), update_modified=False)
		frappe.clear_cache()

	def start_multi_church(self):
		"""One-time move to multi-church: stamp the root on every record, scope every user to it.

		Runs only on the off-to-on transition, never on migrate, so a Church
		permission an administrator deleted afterwards stays deleted.
		"""
		root = root_church()
		multi_church.backfill_root_church(root)
		church_access.grant_root_permission_to_users(root)

	def get_disabled_modules(self):
		"""Return the modules whose box is unchecked."""
		return {module for field, module in MODULE_FIELDS.items() if not cint(self.get(field))}

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

		return self.hide_desktop_icons(should_hide, previously_hidden)

	def sync_other_app_icons(self, previously_hidden):
		"""Hide the desktop icons of Frappe and every other app unless Show Other Apps is ticked."""
		should_hide = set() if cint(self.show_other_apps) else self.get_other_app_icons()
		return self.hide_desktop_icons(should_hide, previously_hidden)

	def get_other_app_icons(self):
		"""Desktop icons that open neither churchit nor one of its modules' sidebars.

		Frappe gives the icons it generates from workspaces no app, so the
		sidebar's module is what ties a Manual icon to churchit. Icons a user
		made for themselves, and the ones Frappe will not let anyone remove,
		are left alone.
		"""
		modules = frappe.get_all("Module Def", filters={"app_name": "churchit"}, pluck="name")
		own_sidebars = set(
			frappe.get_all("Workspace Sidebar", filters={"module": ("in", modules)}, pluck="name")
		)
		icons = frappe.get_all(
			"Desktop Icon",
			filters={"owner": "Administrator", "restrict_removal": 0},
			fields=["name", "app", "link_to"],
		)
		return {icon.name for icon in icons if icon.app != "churchit" and icon.link_to not in own_sidebars}

	def hide_desktop_icons(self, should_hide, previously_hidden):
		"""Hide `should_hide` on the desktop, saved layouts included, and reveal what no longer needs hiding."""
		managed = self.set_flag("Desktop Icon", "hidden", should_hide, previously_hidden)
		self.sync_desktop_layouts(hide=should_hide, reveal=set(previously_hidden) - should_hide)
		return managed

	def sync_desktop_layouts(self, hide, reveal):
		"""Copy the icons' hidden flags into every saved Desktop Layout.

		A user who has rearranged their desktop gets their saved copy of the icons
		drawn instead of the Desktop Icon records, so without this a disabled
		module's icon stays on their desktop.
		"""
		wanted = {**dict.fromkeys(reveal, 0), **dict.fromkeys(hide, 1)}
		for layout in frappe.get_all("Desktop Layout", fields=["name", "layout"]):
			icons = json.loads(layout.layout or "[]")
			changed = [
				icon
				for icon in icons
				if icon.get("name") in wanted and icon.get("hidden") != wanted[icon["name"]]
			]
			for icon in changed:
				icon["hidden"] = wanted[icon["name"]]
			if changed:
				frappe.db.set_value(
					"Desktop Layout", layout.name, "layout", json.dumps(icons), update_modified=False
				)

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

	store_missing_defaults()
	frappe.get_single("Church Features").apply()


def apply_after_app_install(app_name):
	"""after_app_install hook: hide the desktop icons Frappe just made for an app.

	Frappe's own hook creates them first, and both hooks run for churchit's own
	install too, so a new site starts with only churchit on its desktop.
	"""
	apply_on_migrate()


def store_missing_defaults():
	"""Store the default of every field that has no stored value yet.

	Frappe gives a Single its defaults only while it stores nothing at all. Once
	apply() stores managed_records, a checkbox nobody saved loads as 0, so the
	next migrate would hide its module. This also covers a module field added
	by a later release.
	"""
	stored = frappe.db.get_singles_dict("Church Features")
	missing = {
		field.fieldname: field.default
		for field in frappe.get_meta("Church Features").fields
		if field.default is not None and field.fieldname not in stored
	}
	if missing:
		frappe.db.set_single_value("Church Features", missing)
