# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe import _
from frappe.desk.doctype.dock.dock import get_app_dock
from frappe.model.document import Document
from frappe.utils import cint

from churchit.church_foundations import church_access
from churchit.church_scope import root_church
from churchit.church_setup import multi_church

# Check fieldname on Church Features -> the churchit modules it switches. Setup
# leaves out Church Setup, whose Settings page holds these switches.
MODULE_FIELDS = {
	"enable_people": ("Church People",),
	"enable_foundations": ("Church Foundations",),
	"enable_ministries": ("Church Ministries",),
	"enable_prayers": ("Church Prayers",),
	"enable_study": ("Church Study",),
	"enable_communications": ("Church Communications",),
	"enable_missions": ("Church Missions",),
	"enable_operations": ("Church Operations",),
	"enable_finances": ("Church Finances",),
	"enable_website": ("Church Website",),
	"enable_setup": ("Church Summary", "Church Help"),
}


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

		Nothing is deleted and no permission changes: this only flips the
		visibility flags Frappe already honours.
		"""
		disabled = self.get_disabled_modules()
		managed = self.get_managed_records()

		managed["workspaces"] = self.sync_workspaces(disabled, managed.get("workspaces") or [])
		managed["dock"] = self.sync_dock(disabled, managed.get("dock") or [])
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
		return {
			module
			for field, modules in MODULE_FIELDS.items()
			if not cint(self.get(field))
			for module in modules
		}

	def get_managed_records(self):
		"""Return the records this page hid on an earlier save.

		Only these are ever un-hidden again, so a workspace or dock entry
		someone hid by hand stays hidden when its module is on.
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
		except Workspace Managers, and with it out of every sidebar.
		"""
		should_hide = set()
		if disabled_modules:
			should_hide = set(
				frappe.get_all(
					"Workspace", filters={"module": ("in", sorted(disabled_modules))}, pluck="name"
				)
			)

		return self.set_flag("Workspace", "is_hidden", should_hide, previously_hidden)

	def sync_dock(self, disabled_modules, previously_hidden):
		"""Hide the dock entries of the disabled modules, for the site and in each user's own dock.

		A user's own arrangement is laid over the site's and wins, so every
		Churchit layer gets the flag. Returns the entries this page hid.
		"""
		should_hide = set()
		if disabled_modules:
			should_hide = set(
				frappe.get_all("Sidebar", filters={"module": ("in", sorted(disabled_modules))}, pluck="name")
			)
		previously_hidden = set(previously_hidden)
		reveal = previously_hidden - should_hide

		managed = (previously_hidden & should_hide) | self.sync_site_dock(should_hide, reveal)
		for name in frappe.get_all(
			"Dock", filters={"app": "churchit", "standard": 0, "user": ("!=", "")}, pluck="name"
		):
			set_dock_flags(frappe.get_doc("Dock", name), should_hide, reveal)

		return sorted(managed)

	def sync_site_dock(self, should_hide, reveal):
		"""Lay the flags over the site's arrangement of the Churchit dock, made when something needs hiding.

		A saved arrangement is the whole rail, so it also gets each entry
		Churchit ships that it does not name yet. Returns the entries it hid.
		"""
		name = frappe.db.get_value("Dock", {"app": "churchit", "standard": 0, "user": ""})
		if not name and not should_hide:
			return set()

		dock = (
			frappe.get_doc("Dock", name) if name else frappe.get_doc({"doctype": "Dock", "app": "churchit"})
		)
		named = {row.link_to for row in dock.items if row.link_type == "Sidebar"}
		missing = [entry for entry in get_app_dock("churchit") if entry["link_to"] not in named]
		for entry in missing:
			dock.append("items", {"link_type": entry["link_type"], "link_to": entry["link_to"]})

		return set_dock_flags(dock, should_hide, reveal, save=bool(missing) or dock.is_new())

	def set_flag(self, doctype, fieldname, should_hide, previously_hidden):
		"""Hide `should_hide`, reveal what we hid before and no longer need to.

		Returns the records this page is now responsible for. A record that was
		already hidden before we touched it never enters that set, so one hidden
		by hand is not revealed when its module is on.
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


def apply_on_migrate():
	"""after_migrate hook: put the church's choices back.

	Workspaces ship as standard records, so migrate re-imports them whenever
	churchit changes their JSON, resetting the visibility flags this page set.
	It also puts dock entries churchit added since on the site's arrangement.
	"""
	if not frappe.db.exists("DocType", "Church Features"):
		return

	store_missing_defaults()
	frappe.get_single("Church Features").apply()


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
