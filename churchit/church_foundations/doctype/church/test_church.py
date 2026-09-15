# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase


class TestChurch(FrappeTestCase):
	def setUp(self):
		self.church = frappe.db.get_value("Church", {}, "name")
		if not self.church:
			self.church = (
				frappe.get_doc({"doctype": "Church", "church_name": "_Test Church", "abbreviation": "TC"})
				.insert(ignore_permissions=True)
				.name
			)

	def test_only_one_church_is_allowed(self):
		with self.assertRaises(ValidationError):
			frappe.get_doc(
				{"doctype": "Church", "church_name": "_Test Second Church", "abbreviation": "TSC"}
			).insert(ignore_permissions=True)

	def test_the_church_cannot_be_deleted(self):
		with self.assertRaises(ValidationError):
			frappe.delete_doc("Church", self.church, ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Church", self.church))
