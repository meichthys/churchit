# Copyright (c) 2025, meichthys and Contributors
# See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now


class TestFundTransfer(FrappeTestCase):
	def setUp(self):
		self.from_fund = frappe.get_doc(
			{"doctype": "Fund", "fund": "_Test Transfer From"}
		).insert(ignore_permissions=True).name
		self.to_fund = frappe.get_doc(
			{"doctype": "Fund", "fund": "_Test Transfer To"}
		).insert(ignore_permissions=True).name

	def _make_transfer(self, amount=50, **values):
		data = {
			"doctype": "Fund Transfer",
			"from_fund": self.from_fund,
			"to_fund": self.to_fund,
			"amount": amount,
			"date": now(),
		}
		data.update(values)
		return frappe.get_doc(data).insert(ignore_permissions=True)

	def test_same_source_and_destination_rejected(self):
		with self.assertRaises(ValidationError):
			self._make_transfer(to_fund=self.from_fund)

	def test_non_positive_amount_rejected(self):
		with self.assertRaises(ValidationError):
			self._make_transfer(amount=0)

	def test_submit_moves_balance_between_funds(self):
		self._make_transfer(amount=50).submit()
		self.assertEqual(frappe.db.get_value("Fund", self.from_fund, "balance"), -50)
		self.assertEqual(frappe.db.get_value("Fund", self.to_fund, "balance"), 50)

	def test_cancel_reverses_the_transfer(self):
		transfer = self._make_transfer(amount=50)
		transfer.submit()
		transfer.cancel()
		self.assertEqual(frappe.db.get_value("Fund", self.from_fund, "balance"), 0)
		self.assertEqual(frappe.db.get_value("Fund", self.to_fund, "balance"), 0)
