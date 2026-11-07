# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
import os
import tempfile
from unittest.mock import patch

import frappe

from churchit.church_setup.app_clashes import get_record_names, refuse_clashing_app
from churchit.tests.helpers import RollbackEachTest

CLASHING_APP = "_test_clashing_app"


class TestAppClashes(RollbackEachTest):
	def clashing_app(self, doctype, name):
		"""Point Frappe at a temporary app whose one module ships one record."""
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		record = os.path.join(folder.name, "clash_module", frappe.scrub(doctype), frappe.scrub(name))
		os.makedirs(record)
		with open(os.path.join(record, f"{frappe.scrub(name)}.json"), "w") as file:
			json.dump({"doctype": doctype, "name": name}, file)

		get_module_list, get_app_path = frappe.get_module_list, frappe.get_app_path

		def module_list(app):
			return ["Clash Module"] if app == CLASHING_APP else get_module_list(app)

		def app_path(app, *parts):
			return os.path.join(folder.name, *parts) if app == CLASHING_APP else get_app_path(app, *parts)

		for patcher in (
			patch("frappe.get_module_list", side_effect=module_list),
			patch("frappe.get_app_path", side_effect=app_path),
		):
			patcher.start()
			self.addCleanup(patcher.stop)

	def test_an_app_with_a_churchit_doctype_name_is_refused(self):
		self.clashing_app("DocType", "Function")

		with self.assertRaisesRegex(frappe.ValidationError, "Function"):
			refuse_clashing_app(CLASHING_APP)

	def test_an_app_with_a_churchit_report_name_is_refused(self):
		self.clashing_app("Report", "Budget vs Actual")

		with self.assertRaisesRegex(frappe.ValidationError, "Budget vs Actual"):
			refuse_clashing_app(CLASHING_APP)

	def test_an_unmigrated_churchit_record_with_the_apps_name_is_refused(self):
		# The code has renamed it already, but the site holds it under the old name until migrate.
		self.clashing_app("Report", "_Test Unmigrated Report")
		# db_insert, because inserting a standard report would export it to the app in developer mode.
		frappe.get_doc(
			{
				"doctype": "Report",
				"name": "_Test Unmigrated Report",
				"report_name": "_Test Unmigrated Report",
				"ref_doctype": "Church Task",
				"report_type": "Report Builder",
				"is_standard": "Yes",
				"module": "Church Operations",
			}
		).db_insert()

		with self.assertRaisesRegex(frappe.ValidationError, "Migrate this site"):
			refuse_clashing_app(CLASHING_APP)

	def test_a_report_the_church_saved_is_not_taken_for_an_unmigrated_one(self):
		self.clashing_app("Report", "_Test Saved Report")
		frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": "_Test Saved Report",
				"ref_doctype": "Church Task",
				"report_type": "Report Builder",
				"is_standard": "No",
			}
		).insert(ignore_permissions=True)

		refuse_clashing_app(CLASHING_APP)

	def test_the_same_name_on_another_record_type_installs(self):
		self.clashing_app("Report", "Function")

		refuse_clashing_app(CLASHING_APP)

	def test_an_app_without_shared_names_installs(self):
		refuse_clashing_app("frappe")
		if "payments" in frappe.get_all_apps():
			refuse_clashing_app("payments")

	def test_frappe_learning_shares_function(self):
		if "lms" not in frappe.get_all_apps():
			self.skipTest("Frappe Learning is not on this bench")
		self.assertEqual(get_record_names("lms") & get_record_names("churchit"), {("DocType", "Function")})

	def test_erpnext_shares_no_record(self):
		if "erpnext" not in frappe.get_all_apps():
			self.skipTest("ERPNext is not on this bench")
		self.assertFalse(get_record_names("erpnext") & get_record_names("churchit"))

	def test_migrate_runs_no_check(self):
		hooks = [*frappe.get_hooks("before_migrate"), *frappe.get_hooks("after_migrate")]
		self.assertFalse([hook for hook in hooks if "app_clashes" in hook])
