# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
import os
import tempfile
from unittest.mock import patch

import frappe

from churchit.ai.policy import PAGE_NAME
from churchit.church_setup.app_clashes import get_record_names, refuse_clashing_app
from churchit.church_setup.app_names import INSTALL_ROUTES, ROUTE, get_shared_names
from churchit.patches.after_install import WEB_PAGES
from churchit.tests.helpers import RollbackEachTest

CLASHING_APP = "_test_clashing_app"


class TestAppClashes(RollbackEachTest):
	def clashing_app(self, doctype, name):
		"""Point Frappe at a temporary app whose one module ships one record."""
		folder = frappe.scrub(name)
		self.clashing_file(
			f"clash_module/{frappe.scrub(doctype)}/{folder}/{folder}.json", {"doctype": doctype, "name": name}
		)

	def clashing_file(self, path, content):
		"""Point Frappe at a temporary app with the module Clash Module that holds one file at *path*."""
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		os.makedirs(os.path.dirname(os.path.join(folder.name, path)))
		with open(os.path.join(folder.name, path), "w") as file:
			file.write(content if isinstance(content, str) else json.dumps(content))

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

	def test_a_name_in_other_letters_is_refused(self):
		# MariaDB compares names without case, so the two would be one record.
		self.clashing_app("DocType", "FUNCTION")

		with self.assertRaisesRegex(frappe.ValidationError, "Function"):
			refuse_clashing_app(CLASHING_APP)

	def test_a_record_deeper_in_a_module_is_refused(self):
		self.clashing_file(
			"clash_module/doctype/thing/kanban_board/care_requests.json",
			{"doctype": "Kanban Board", "name": "Care Requests"},
		)

		with self.assertRaisesRegex(frappe.ValidationError, "Care Requests"):
			refuse_clashing_app(CLASHING_APP)

	def test_a_fixture_with_a_churchit_name_is_refused(self):
		self.clashing_file("fixtures/role.json", [{"doctype": "Role", "name": "Church Manager"}])

		with self.assertRaisesRegex(frappe.ValidationError, "Church Manager"):
			refuse_clashing_app(CLASHING_APP)

	def test_a_page_on_a_churchit_route_is_refused(self):
		self.clashing_file("www/calendar.html", "<p>Another calendar</p>")

		with self.assertRaisesRegex(frappe.ValidationError, "calendar"):
			refuse_clashing_app(CLASHING_APP)

	def test_the_same_name_on_another_record_type_installs(self):
		self.clashing_app("Report", "Function")

		refuse_clashing_app(CLASHING_APP)

	def test_an_app_without_shared_names_installs(self):
		refuse_clashing_app("frappe")
		if "payments" in frappe.get_all_apps():
			refuse_clashing_app("payments")

	def test_frappe_shares_only_the_pages_churchit_replaces(self):
		# refuse_clashing_installed_apps checks Frappe on every new site, and leaves these routes out.
		shared = get_shared_names(get_record_names("churchit"), get_record_names("frappe"))
		self.assertEqual(
			{(name.doctype, name.name) for name, _other in shared},
			{(ROUTE, "about"), (ROUTE, "contact"), (ROUTE, "portal")},
		)

	def test_install_routes_are_the_pages_after_install_makes(self):
		routes = {page["route"] for page in WEB_PAGES} | {PAGE_NAME}
		self.assertEqual(set(INSTALL_ROUTES["churchit"]), routes)

	def test_an_app_page_on_a_route_churchit_makes_at_install_is_refused(self):
		self.clashing_file("www/sermons.html", "<p>Another sermon list</p>")

		with self.assertRaisesRegex(frappe.ValidationError, "sermons"):
			refuse_clashing_app(CLASHING_APP)

	def test_frappe_learning_shares_function(self):
		if "lms" not in frappe.get_all_apps():
			self.skipTest("Frappe Learning is not on this bench")
		shared = get_shared_names(get_record_names("churchit"), get_record_names("lms"))
		self.assertEqual([(name.doctype, name.name) for name, _other in shared], [("DocType", "Function")])

	def test_erpnext_shares_no_record(self):
		if "erpnext" not in frappe.get_all_apps():
			self.skipTest("ERPNext is not on this bench")
		self.assertFalse(get_shared_names(get_record_names("churchit"), get_record_names("erpnext")))

	def test_frappe_hr_shares_no_record(self):
		if "hrms" not in frappe.get_all_apps():
			self.skipTest("Frappe HR is not on this bench")
		self.assertFalse(get_shared_names(get_record_names("churchit"), get_record_names("hrms")))

	def test_migrate_runs_no_check(self):
		hooks = [*frappe.get_hooks("before_migrate"), *frappe.get_hooks("after_migrate")]
		self.assertFalse([hook for hook in hooks if "app_clashes" in hook])
