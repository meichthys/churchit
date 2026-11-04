# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.core.doctype.doctype.doctype import clear_permissions_cache
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.desk.search import search_link
from frappe.permissions import add_permission

from churchit.patches.v1_0 import let_church_roles_read_addresses, show_address_fields_for_erpnext
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_address

CHURCH_HIDDEN_FIELDS = ("email_id", "phone", "fax", "is_primary_address", "is_shipping_address", "disabled")
ERPNEXT_FIELDS = ("is_your_company_address", "tax_category")


class TestAddressCustomization(RollbackEachTest):
	"""The church Address form stays lean, but the fields ERPNext needs show when ERPNext is installed."""

	def test_no_setter_hides_a_field_that_erpnext_needs(self):
		meta = frappe.get_meta("Address")
		fieldnames = [name for name in CHURCH_HIDDEN_FIELDS + ERPNEXT_FIELDS if meta.has_field(name)]

		self.assertEqual([name for name in fieldnames if meta.get_field(name).hidden], [])

	def test_the_church_form_shows_the_unused_fields_only_with_erpnext(self):
		visibility = {}
		section_depends_on = None
		for df in frappe.get_meta("Address").fields:
			if df.fieldtype == "Section Break":
				section_depends_on = df.depends_on
			visibility[df.fieldname] = df.depends_on or section_depends_on

		for fieldname in CHURCH_HIDDEN_FIELDS:
			with self.subTest(fieldname=fieldname):
				self.assertRegex(visibility[fieldname] or "", r"frappe\.boot\.versions.*\berpnext\b")

	def test_patch_removes_the_old_hidden_setters(self):
		shipped = (*CHURCH_HIDDEN_FIELDS, "is_your_company_address")
		for fieldname in shipped:
			make_property_setter(
				"Address", fieldname, "hidden", "1", "Check", validate_fields_for_doctype=False
			)

		show_address_fields_for_erpnext.execute()

		self.assertFalse(
			frappe.db.exists(
				"Property Setter",
				{"doc_type": "Address", "property": "hidden", "field_name": ("in", shipped)},
			)
		)

	def test_an_address_link_shows_the_street_and_is_found_by_city(self):
		address = make_address("_Test Street Title", address_line1="17 Juniper Court", city="Quillfield")

		results = search_link("Address", "Quillfield")

		self.assertEqual(
			[(row["value"], row["label"]) for row in results], [(address.name, "17 Juniper Court")]
		)
		self.assertIn("Quillfield", results[0]["description"])


class TestAddressReaders(RollbackEachTest):
	"""Frappe gives a role only the addresses it added, so the Map of Addresses was empty for staff."""

	def setUp(self):
		super().setUp()
		frappe.db.delete("Custom DocPerm", {"parent": "Address"})
		clear_permissions_cache("Address")
		self.addCleanup(clear_permissions_cache, "Address")

	def test_staff_read_every_address_but_change_only_their_own(self):
		staff = ensure_user("_test-address-reader@example.com", "Address Reader", roles=("Church Staff",))
		address = make_address("_Test Address Reader").name
		self.assertFalse(frappe.has_permission("Address", "read", doc=address, user=staff))

		let_church_roles_read_addresses.execute()

		self.assertTrue(frappe.has_permission("Address", "read", doc=address, user=staff))
		self.assertFalse(frappe.has_permission("Address", "write", doc=address, user=staff))

	def test_the_rules_of_frappe_and_other_apps_stay(self):
		"""ERPNext adds Address read for Accounts Manager the same way; a role stands in for it here."""
		add_permission("Address", "Church Finance")

		let_church_roles_read_addresses.execute()
		let_church_roles_read_addresses.execute()

		readers = frappe.get_all("Custom DocPerm", filters={"parent": "Address", "read": 1}, pluck="role")
		for role in (
			"System Manager",
			"Church Finance",
			"Church Manager",
			"Church Staff",
			"Church People Editor",
		):
			self.assertEqual(readers.count(role), 1, role)
