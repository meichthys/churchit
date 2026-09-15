# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase


class TestMissionaryAgency(FrappeTestCase):
	"""The shared contact-table rules are covered in churchit.tests.test_contacts;
	these only prove this doctype runs them."""

	def _agency(self, agency_name, **values):
		return frappe.get_doc({"doctype": "Missionary Agency", "agency_name": agency_name, **values}).insert(
			ignore_permissions=True
		)

	def test_first_email_becomes_primary(self):
		agency = self._agency(
			"_Test Sending Agency",
			emails=[{"email_address": "one@example.com"}, {"email_address": "two@example.com"}],
		)
		self.assertEqual([row.is_primary for row in agency.emails], [1, 0])

	def test_values_are_trimmed(self):
		agency = self._agency("_Test Trimming Agency", emails=[{"email_address": "  pad@example.com  "}])
		self.assertEqual(agency.emails[0].email_address, "pad@example.com")

	def test_duplicate_emails_are_rejected(self):
		with self.assertRaises(ValidationError):
			self._agency(
				"_Test Duplicate Agency",
				emails=[{"email_address": "same@example.com"}, {"email_address": "SAME@example.com"}],
			)
