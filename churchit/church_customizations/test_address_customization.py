# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from churchit.patches.v1_0 import show_address_fields_for_erpnext
from churchit.tests.helpers import RollbackEachTest

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
