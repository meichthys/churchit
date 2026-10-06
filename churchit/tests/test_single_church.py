# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The app with the multi-church switch off, which is how most churches run it.

Every scoping helper has two paths, and the one taken depends on a site-wide
switch. A test site with branches proves only the multi-church path, so these
turn the switch off first and walk the surfaces the scoping touched: the reports,
the public pages, a printed bulletin and a saved record.
"""

import importlib

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.doctype.church.church import selected_church_name
from churchit.church_scope import is_multi_church
from churchit.tests.helpers import ensure, ensure_root_church, force_single_church, make_function
from churchit.tests.test_reports_execute import report_modules

# Pages a signed-in staff user reaches. Guest-only redirects are covered per page.
PUBLIC_PAGES = ("about", "attendance", "bulletins", "calendar", "contact", "give", "statements")


class TestSingleChurch(FrappeTestCase):
	"""Switched off once for the class: flipping the switch rewrites every church field."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		force_single_church()

	def setUp(self):
		frappe.local.form_dict = frappe._dict()
		self.assertFalse(is_multi_church())

	def test_a_new_record_is_saved_without_a_church(self):
		"""Nothing stamps a church while the switch is off, and nothing refuses the save."""
		person = frappe.get_doc({"doctype": "Person", "first_name": "_Test Single Church"}).insert(
			ignore_permissions=True
		)
		self.assertFalse(person.church)

	def test_the_one_church_is_what_every_page_and_letterhead_resolves_to(self):
		self.assertEqual(selected_church_name(), self.root)

	def test_every_report_runs(self):
		"""The scoped reports return their own rows, not an empty set, with no church anywhere."""
		failures = []
		for module_name in sorted(report_modules()):
			try:
				columns, data = importlib.import_module(module_name).execute({})[:2]
				assert isinstance(columns, list) and columns, "no columns"
				assert isinstance(data, list), "data is not a list"
			except Exception as exc:
				failures.append(f"{module_name}: {exc!r}")
		self.assertEqual(failures, [])

	def test_every_public_page_renders(self):
		failures = []
		for page in PUBLIC_PAGES:
			try:
				module = importlib.import_module(f"churchit.www.{page}")
				module.get_context(frappe._dict())
			except Exception as exc:
				failures.append(f"{page}: {exc!r}")
		self.assertEqual(failures, [])

	def test_the_locations_page_is_not_served(self):
		"""One church has no locations to list, so the route is left to a 404."""
		module = importlib.import_module("churchit.www.locations")
		with self.assertRaises(frappe.PageDoesNotExistError):
			module.get_context(frappe._dict())

	def test_a_bulletin_prints_the_sites_own_church(self):
		ensure("Function Type", {"type": "_Test Single Church Service"})
		function = make_function("_Test Single Church Service")
		bulletin = frappe.get_doc({"doctype": "Bulletin", "function": function.name}).insert(
			ignore_permissions=True
		)

		self.assertFalse(bulletin.church)
		self.assertEqual(bulletin.church_doc.name, self.root)
		self.assertEqual(bulletin.contact_information.name, bulletin.church_doc.church_name)
