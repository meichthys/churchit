# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
import re

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now

from churchit.church_setup.doctype.church_features.church_features import (
	MODULE_FIELDS,
	apply_on_migrate,
)
from churchit.tests.helpers import (
	ensure,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_branch,
	make_person,
	set_multi_church,
)


class TestChurchFeatures(FrappeTestCase):
	def setUp(self):
		self.features = frappe.get_single("Church Features")
		self.addCleanup(self.restore)

	def restore(self):
		features = frappe.get_single("Church Features")
		for field in MODULE_FIELDS:
			features.set(field, 1)
		features.save()

	def test_disabling_a_module_hides_its_workspaces(self):
		self.features.enable_missions = 0
		self.features.save()

		self.assertEqual(frappe.db.get_value("Workspace", "Missions", "is_hidden"), 1)
		self.assertEqual(frappe.db.get_value("Workspace", "Manual: Missions", "is_hidden"), 1)
		self.assertEqual(frappe.db.get_value("Desktop Icon", "Missions", "hidden"), 1)
		self.assertIn("Church Missions", frappe.get_doc("User", "Administrator").get_blocked_modules())

	def test_re_enabling_restores_what_was_hidden(self):
		self.features.enable_missions = 0
		self.features.save()

		features = frappe.get_single("Church Features")
		features.enable_missions = 1
		features.save()

		self.assertEqual(frappe.db.get_value("Workspace", "Missions", "is_hidden"), 0)
		self.assertEqual(frappe.db.get_value("Desktop Icon", "Missions", "hidden"), 0)
		self.assertNotIn("Church Missions", frappe.get_doc("User", "Administrator").get_blocked_modules())

	def test_workspaces_that_ship_hidden_stay_hidden(self):
		"""Customizations workspaces ship with is_hidden set; toggling the module
		off and back on must not reveal them."""
		self.features.enable_customizations = 0
		self.features.save()

		features = frappe.get_single("Church Features")
		features.enable_customizations = 1
		features.save()

		self.assertEqual(frappe.db.get_value("Workspace", "Tools", "is_hidden"), 1)
		self.assertEqual(frappe.db.get_value("Workspace", "Build", "is_hidden"), 1)

	def test_migrate_stores_the_defaults_nobody_saved(self):
		"""Frappe gives a Single its defaults only while it stores nothing. A site that
		never saved this page held only managed_records after its first migrate, so
		every box loaded unchecked and the next migrate hid every module."""
		frappe.db.delete("Singles", {"doctype": "Church Features"})
		frappe.db.set_single_value("Church Features", "managed_records", "{}")

		apply_on_migrate()

		features = frappe.get_single("Church Features")
		self.assertEqual(features.enable_missions, 1)
		self.assertEqual(features.enable_multi_church, 0)
		self.assertEqual(frappe.db.get_value("Desktop Icon", "Missions", "hidden"), 0)
		self.assertEqual(frappe.db.get_value("Workspace", "Missions", "is_hidden"), 0)

	def test_settings_workspace_survives_disabling_setup(self):
		self.features.enable_setup = 0
		self.features.save()

		self.assertEqual(frappe.db.get_value("Workspace", "Summary", "is_hidden"), 1)
		self.assertEqual(frappe.db.get_value("Workspace", "Settings", "is_hidden"), 0)
		self.assertEqual(frappe.db.get_value("Desktop Icon", "Settings", "hidden"), 0)

	def test_every_workspace_header_link_has_a_desktop_icon(self):
		"""The header shows a module only while its desktop icon is visible, so a
		link whose label matches no icon would never show."""
		with open(frappe.get_app_path("churchit", "fixtures", "custom_html_block.json")) as file:
			header = next(block for block in json.load(file) if block["name"] == "WorkspaceHeader")
		labels = re.findall(r'<span class="ws-label">([^<]+)</span>', header["html"])

		self.assertEqual(len(labels), 13)
		self.assertEqual([label for label in labels if not frappe.db.exists("Desktop Icon", label)], [])


class TestMultiChurchSwitch(FrappeTestCase):
	def setUp(self):
		force_single_church()
		self.root = ensure_root_church()
		self.user = ensure_user("_test_scope_user@example.com", "Scope")
		self.person = make_person("_Test Scoped", "Person")
		self.collection = self.make_submitted_collection()

	def tearDown(self):
		# Deepest first: a nested set refuses to delete a church that still has branches.
		for name in frappe.get_all(
			"Church", filters={"parent_church": ("is", "set")}, pluck="name", order_by="lft desc"
		):
			frappe.delete_doc("Church", name, ignore_permissions=True, force=True)
		set_multi_church(False)

	def make_submitted_collection(self):
		fund = ensure("Fund", {"fund": "_Test Switch Fund"})
		payment_type = ensure("Payment Type", {"type": "Cash"})
		collection = frappe.get_doc({"doctype": "Collection", "date": now(), "expected_total": 10})
		collection.append("donations", {"payment_type": payment_type, "fund": fund, "amount": 10})
		collection.insert(ignore_permissions=True)
		collection.submit()
		return collection

	def field_setter(self, doctype, fieldname, prop):
		return frappe.db.get_value(
			"Property Setter",
			{"doc_type": doctype, "field_name": fieldname, "property": prop},
			"value",
		)

	def church_setter(self, doctype, prop):
		return self.field_setter(doctype, "church", prop)

	def user_permission(self, user):
		return frappe.db.get_value(
			"User Permission",
			{"user": user, "allow": "Church"},
			["name", "for_value", "hide_descendants", "is_default"],
			as_dict=True,
		)

	def test_enabling_reveals_the_field_and_backfills_records(self):
		self.assertFalse(frappe.db.get_value("Person", self.person.name, "church"))

		set_multi_church(True)

		self.assertEqual(self.church_setter("Person", "hidden"), "0")
		self.assertEqual(self.church_setter("Function", "in_standard_filter"), "1")
		self.assertEqual(frappe.db.get_value("Person", self.person.name, "church"), self.root)
		self.assertEqual(frappe.db.get_value("Collection", self.collection.name, "church"), self.root)

	def test_enabling_scopes_every_user_to_the_root(self):
		set_multi_church(True)

		permission = self.user_permission(self.user)
		self.assertEqual(permission.for_value, self.root)
		self.assertEqual(permission.hide_descendants, 1)
		self.assertEqual(permission.is_default, 1)
		self.assertIsNone(self.user_permission("Administrator"))

	def test_a_deleted_permission_is_not_recreated(self):
		set_multi_church(True)
		frappe.delete_doc("User Permission", self.user_permission(self.user).name, ignore_permissions=True)

		frappe.get_single("Church Features").save()
		apply_on_migrate()

		self.assertIsNone(self.user_permission(self.user))

	def test_new_records_default_to_the_root_church(self):
		set_multi_church(True)
		person = make_person("_Test Defaulted", "Person")
		self.assertEqual(person.church, self.root)

	def test_enabling_reveals_who_shared_a_record(self):
		"""Without Shared By, a record the main church shared looked like the branch's own."""
		set_multi_church(True)

		self.assertEqual(self.field_setter("Song", "is_shared", "hidden"), "0")
		self.assertEqual(self.field_setter("Song", "shared_by_church", "hidden"), "0")
		self.assertEqual(self.field_setter("Song", "shared_by_church", "in_standard_filter"), "1")

	def test_the_sharing_fields_are_only_revealed_where_sharing_is_offered(self):
		set_multi_church(True)

		self.assertIsNone(self.field_setter("Person", "is_shared", "hidden"))
		self.assertIsNone(self.field_setter("Person", "shared_by_church", "hidden"))

	def test_disabling_is_blocked_while_branches_exist(self):
		set_multi_church(True)
		make_branch("_Test Switch Branch", "SB")
		with self.assertRaises(ValidationError):
			set_multi_church(False)

	def test_disabling_removes_the_property_setters(self):
		set_multi_church(True)
		set_multi_church(False)
		self.assertIsNone(self.church_setter("Person", "hidden"))
		self.assertIsNone(self.field_setter("Song", "is_shared", "hidden"))
		self.assertIsNone(self.field_setter("Song", "shared_by_church", "hidden"))

	def test_enabling_replaces_a_setter_that_hides_the_field(self):
		make_property_setter("Person", "church", "hidden", "1", "Check", validate_fields_for_doctype=False)

		set_multi_church(True)

		self.assertEqual(self.church_setter("Person", "hidden"), "0")
		self.assertEqual(frappe.db.count("Property Setter", {"name": "Person-church-hidden"}), 1)
		self.assertFalse(frappe.get_meta("Person").get_field("church").hidden)
