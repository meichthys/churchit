# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from pathlib import Path

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase
from frappe.utils.jinja import render_template
from frappe.utils.nestedset import NestedSetMultipleRootsError

from churchit.church_foundations.church_access import set_user_church, user_church_permissions
from churchit.church_foundations.doctype.church.church import inherited_value
from churchit.church_scope import allowed_churches
from churchit.tests.helpers import (
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_address,
	make_branch,
	set_multi_church,
)


class TestChurch(FrappeTestCase):
	def setUp(self):
		force_single_church()
		self.church = ensure_root_church()

	def test_only_one_church_is_allowed(self):
		with self.assertRaises(ValidationError):
			frappe.get_doc(
				{"doctype": "Church", "church_name": "_Test Second Church", "abbreviation": "TSC"}
			).insert(ignore_permissions=True)

	def test_the_church_cannot_be_deleted(self):
		with self.assertRaises(ValidationError):
			frappe.delete_doc("Church", self.church, ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Church", self.church))


class TestMultiChurch(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		set_multi_church(True)
		cls.addClassCleanup(frappe.clear_cache)

	def test_branch_needs_a_group_parent(self):
		frappe.db.set_value("Church", self.root, "is_group", 0)
		with self.assertRaises(ValidationError):
			frappe.get_doc(
				{
					"doctype": "Church",
					"church_name": "_Test Orphan Branch",
					"abbreviation": "OB",
					"parent_church": self.root,
				}
			).insert(ignore_permissions=True)

	def test_deleting_a_branch_moves_its_users_up_to_the_parent(self):
		"""A permission left on a deleted church hides every other church's records;
		dropping it instead would leave the user seeing them all."""
		branch = make_branch("_Test Closing Branch", "TCB")
		user = ensure_user("_test_closing_branch@example.com", "Closing")
		set_user_church(user, branch)

		frappe.delete_doc("Church", branch, ignore_permissions=True, force=True)

		(permission,) = user_church_permissions(user)
		self.assertEqual(permission.for_value, self.root)
		self.assertEqual(allowed_churches(user), [self.root])

	def test_two_churches_cannot_share_an_abbreviation(self):
		"""The member Email Group is named after the church, but a shared abbreviation
		once merged two congregations' recipient lists."""
		branch = make_branch("_Test Abbreviation Owner", "TAO")
		abbreviation = frappe.db.get_value("Church", branch, "abbreviation")

		with self.assertRaises(frappe.UniqueValidationError):
			frappe.get_doc(
				{
					"doctype": "Church",
					"church_name": "_Test Abbreviation Thief",
					"abbreviation": abbreviation,
					"parent_church": self.root,
				}
			).insert(ignore_permissions=True)

	def test_branch_is_allowed_under_a_group(self):
		branch = make_branch("_Test Branch", "TB")
		self.assertEqual(frappe.db.get_value("Church", branch, "parent_church"), self.root)

	def test_second_root_is_blocked(self):
		with self.assertRaises(NestedSetMultipleRootsError):
			frappe.get_doc(
				{"doctype": "Church", "church_name": "_Test Second Root", "abbreviation": "SR"}
			).insert(ignore_permissions=True)

	def test_root_cannot_be_deleted_but_a_branch_can(self):
		branch = make_branch("_Test Deletable Branch", "DB")
		with self.assertRaises(ValidationError):
			frappe.delete_doc("Church", self.root, ignore_permissions=True)
		frappe.delete_doc("Church", branch, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Church", branch))

	def test_inherited_value_walks_up_the_tree(self):
		frappe.db.set_value("Church", self.root, "tax_id", "12-3456789")
		branch = make_branch("_Test Inheriting Branch", "IB")
		self.assertEqual(inherited_value(branch, "tax_id"), "12-3456789")
		frappe.db.set_value("Church", branch, "tax_id", "98-7654321")
		self.assertEqual(inherited_value(branch, "tax_id"), "98-7654321")


class TestLetterhead(FrappeTestCase):
	"""The shipped letterhead, rendered from the fixture rather than the site.

	A letterhead that throws takes every print format and PDF with it, and the
	fixture only reaches a site on migrate, so the JSON is what is tested here.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		set_multi_church(True)
		cls.addClassCleanup(frappe.clear_cache)

	def render(self, doc=None):
		path = (
			Path(frappe.get_app_path("churchit"))
			/ "church_customizations/letter_head/church_letter_head/church_letter_head.json"
		)
		return render_template(json.loads(path.read_text())["content"], {"doc": doc})

	def test_it_renders_the_church_name(self):
		name = frappe.db.get_value("Church", self.root, "church_name")
		self.assertIn(name, self.render())

	def test_a_branch_document_prints_its_own_church(self):
		branch = make_branch("_Test Letterhead Branch", "LHB")
		fund = frappe.get_doc({"doctype": "Fund", "fund": "_Test Letterhead Fund", "church": branch}).insert(
			ignore_permissions=True
		)

		html = self.render(fund)
		self.assertIn("_Test Letterhead Branch", html)
		self.assertNotIn(frappe.db.get_value("Church", self.root, "church_name"), html)

	def test_the_address_is_the_church_s_own(self):
		address = make_address("_Test Letterhead Address", address_line1="7 Steeple Way", city="Bethel")
		frappe.db.set_value("Church", self.root, "address", address.name)
		frappe.clear_document_cache("Church", self.root)

		html = self.render()
		self.assertIn("7 Steeple Way", html)
		self.assertIn("Bethel", html)

	def test_it_omits_the_contact_line_rather_than_inventing_one(self):
		frappe.db.set_value("Church", self.root, "address", None)
		frappe.clear_document_cache("Church", self.root)
		settings = frappe.get_doc("Contact Us Settings")
		settings.update({"phone": "", "email_id": ""})
		settings.save(ignore_permissions=True)

		html = self.render()
		self.assertIn(frappe.db.get_value("Church", self.root, "church_name"), html)
		self.assertNotIn("margin-top: 4px", html)
