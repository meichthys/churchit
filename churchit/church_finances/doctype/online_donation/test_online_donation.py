# Copyright (c) 2026, meichthys and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestOnlineDonation(FrappeTestCase):
	def setUp(self):
		# "Online" Payment Type is required for the recorded Collection's Donation row.
		if not frappe.db.exists("Payment Type", "Online"):
			frappe.get_doc({"doctype": "Payment Type", "type": "Online"}).insert(
				ignore_permissions=True
			)

	def _make_fund(self):
		return frappe.get_doc(
			{"doctype": "Fund", "fund": "Test Giving Fund"}
		).insert(ignore_permissions=True)

	def _make_gift(self, fund, amount, person=None, email=None, donor_name=None):
		return frappe.get_doc(
			{
				"doctype": "Online Donation",
				"amount": amount,
				"fund": fund.name,
				"person": person,
				"email": email,
				"donor_name": donor_name,
				"currency": "USD",
				"status": "Pending",
			}
		).insert(ignore_permissions=True)

	def test_payment_authorized_records_submitted_collection(self):
		fund = self._make_fund()
		gift = self._make_gift(fund, 50, donor_name="Test Giver", email="giver@example.com")

		redirect = gift.on_payment_authorized("Completed")
		gift.reload()

		# The gift is marked paid and points at its Collection
		self.assertEqual(gift.status, "Paid")
		self.assertTrue(gift.collection)
		self.assertIn(f"success={gift.name}", redirect)

		# A submitted, single-row Collection was created with the right donation
		collection = frappe.get_doc("Collection", gift.collection)
		self.assertEqual(collection.docstatus, 1)
		self.assertEqual(len(collection.donations), 1)
		row = collection.donations[0]
		self.assertEqual(row.payment_type, "Online")
		self.assertEqual(row.fund, fund.name)
		self.assertEqual(row.amount, 50)

		# The fund balance increased by the gift amount
		self.assertEqual(frappe.db.get_value("Fund", fund.name, "balance"), 50)

	def test_anonymous_gift_records_without_person(self):
		fund = self._make_fund()
		gift = self._make_gift(fund, 25, donor_name="Anon", email="anon@example.com")

		gift.on_payment_authorized("Completed")
		gift.reload()

		self.assertEqual(gift.status, "Paid")
		collection = frappe.get_doc("Collection", gift.collection)
		self.assertFalse(collection.donations[0].person)

	def test_failed_payment_marks_failed(self):
		fund = self._make_fund()
		gift = self._make_gift(fund, 10, donor_name="Nope", email="n@example.com")

		gift.on_payment_authorized("Declined")
		gift.reload()

		self.assertEqual(gift.status, "Failed")
		self.assertFalse(gift.collection)

	def test_authorized_is_idempotent(self):
		fund = self._make_fund()
		gift = self._make_gift(fund, 30, donor_name="Once", email="o@example.com")

		gift.on_payment_authorized("Completed")
		gift.reload()
		first_collection = gift.collection

		# Re-firing the callback must not record a second Collection
		gift.on_payment_authorized("Completed")
		gift.reload()
		self.assertEqual(gift.collection, first_collection)
		self.assertEqual(frappe.db.get_value("Fund", fund.name, "balance"), 30)
