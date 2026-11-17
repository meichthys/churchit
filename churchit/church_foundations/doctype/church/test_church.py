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

	def insert_branch(self, church_name, abbreviation, parent):
		return frappe.get_doc(
			{
				"doctype": "Church",
				"church_name": church_name,
				"abbreviation": abbreviation,
				"parent_church": parent,
			}
		).insert(ignore_permissions=True)

	def test_the_main_church_becomes_a_group_with_its_first_branch(self):
		"""A first branch can have no other parent, so nobody has to leave the form to tick Is Group."""
		frappe.db.set_value("Church", self.root, "is_group", 0)
		frappe.local.message_log = []

		self.insert_branch("_Test First Branch", "TFB", self.root)

		self.assertTrue(frappe.db.get_value("Church", self.root, "is_group"))
		(steps,) = frappe.local.message_log
		self.assertEqual(steps.title, "Next Steps for _Test First Branch")

	def test_a_new_branch_opens_at_once_to_its_creator_who_includes_branches(self):
		"""Frappe caches each user's churches with their branches, so a new branch must clear the creator's."""
		user = ensure_user("_test_branch_creator@example.com", "Creator", roles=("Church Manager",))
		set_user_church(user, self.root)
		permission = frappe.get_doc("User Permission", user_church_permissions(user)[0].name)
		permission.hide_descendants = 0
		permission.save(ignore_permissions=True)
		self.addCleanup(frappe.cache.hdel, "user_permissions", user)
		self.assertIn(self.root, allowed_churches(user))

		frappe.set_user(user)
		self.addCleanup(frappe.set_user, "Administrator")
		branch = self.insert_branch("_Test Creator Branch", "TCRB", self.root).name

		self.assertIn(branch, allowed_churches(user))

	def test_a_branch_under_another_branch_needs_it_to_be_a_group(self):
		parent = make_branch("_Test Leaf Parent", "TLP")
		with self.assertRaisesRegex(ValidationError, "Check Is Group on _Test Leaf Parent "):
			self.insert_branch("_Test Orphan Branch", "OB", parent)

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
		"""A shared abbreviation once merged two congregations' member email lists."""
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
		root_name = frappe.db.get_value("Church", self.root, "church_name")
		with self.assertRaisesRegex(NestedSetMultipleRootsError, f"{root_name} is already the main church"):
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

	def test_a_branch_prints_its_parents_website_until_it_has_its_own(self):
		frappe.db.set_value("Church", self.root, "website", "https://main.example.org/")
		branch = make_branch("_Test Website Branch", "WB")
		self.assertEqual(frappe.get_doc("Church", branch).printed_website, "main.example.org")
		frappe.db.set_value("Church", branch, "website", "http://branch.example.org")
		self.assertEqual(frappe.get_doc("Church", branch).printed_website, "branch.example.org")


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
