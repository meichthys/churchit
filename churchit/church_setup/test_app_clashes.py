# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
import os
import tempfile
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_setup.app_clashes import get_doctype_names, refuse_clashing_app

CLASHING_APP = "_test_clashing_app"


class TestAppClashes(FrappeTestCase):
	def clashing_app(self):
		"""Point Frappe at a temporary app whose one module ships a doctype named Function."""
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		doctype = os.path.join(folder.name, "clash_module", "doctype", "function")
		os.makedirs(doctype)
		with open(os.path.join(doctype, "function.json"), "w") as file:
			json.dump({"doctype": "DocType", "name": "Function"}, file)

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
		self.clashing_app()

		with self.assertRaisesRegex(frappe.ValidationError, "Function"):
			refuse_clashing_app(CLASHING_APP)

	def test_an_app_without_shared_names_installs(self):
		refuse_clashing_app("payments")
		refuse_clashing_app("frappe")

	def test_frappe_learning_shares_function(self):
		if "lms" not in frappe.get_all_apps():
			self.skipTest("Frappe Learning is not on this bench")
		self.assertEqual(get_doctype_names("lms") & get_doctype_names("churchit"), {"Function"})

	def test_migrate_runs_no_check(self):
		hooks = [*frappe.get_hooks("before_migrate"), *frappe.get_hooks("after_migrate")]
		self.assertFalse([hook for hook in hooks if "app_clashes" in hook])
