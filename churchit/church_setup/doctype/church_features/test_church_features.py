# Copyright (c) 2026, meichthys and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_setup.doctype.church_features.church_features import MODULE_FIELDS


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

	def test_unset_checks_count_as_enabled(self):
		"""A Single nobody has saved yet reads every check as None. Those must
		not be treated as "off", or the first after_migrate hides the whole app."""
		fresh = frappe.new_doc("Church Features")
		for field in MODULE_FIELDS:
			fresh.set(field, None)

		self.assertEqual(fresh.get_disabled_modules(), set())

	def test_settings_workspace_survives_disabling_setup(self):
		self.features.enable_setup = 0
		self.features.save()

		self.assertEqual(frappe.db.get_value("Workspace", "Welcome", "is_hidden"), 1)
		self.assertEqual(frappe.db.get_value("Workspace", "Settings", "is_hidden"), 0)
		self.assertEqual(frappe.db.get_value("Desktop Icon", "Settings", "hidden"), 0)
