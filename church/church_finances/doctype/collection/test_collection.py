# Copyright (c) 2025, meichthys and Contributors
# See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestCollection(FrappeTestCase):
	def setUp(self):
		self.fund = frappe.get_doc(
			{"doctype": "Fund", "fund": "_Test Collection Fund"}
		).insert(ignore_permissions=True).name
		self.payment_type = _ensure("Payment Type", {"type": "Cash"}, {"type": "Cash"})

	def _make_collection(self, amount=200, expected_total=None):
		collection = frappe.get_doc(
			{
				"doctype": "Collection",
				"date": now(),
				"expected_total": amount if expected_total is None else expected_total,
			}
		)
		collection.append(
			"donations",
			{"payment_type": self.payment_type, "fund": self.fund, "amount": amount},
		)
		return collection.insert(ignore_permissions=True)

	def test_totals_and_breakdowns_computed(self):
		collection = self._make_collection(amount=200)
		self.assertEqual(collection.total_amount, 200)
		self.assertEqual(collection.imbalance, 0)
		self.assertEqual({f.fund: f.total for f in collection.fund_totals}, {self.fund: 200})
		self.assertEqual(
			{p.payment_type: p.total for p in collection.payment_type_totals},
			{self.payment_type: 200},
		)

	def test_imbalance_computed_from_expected_total(self):
		collection = self._make_collection(amount=200, expected_total=250)
		self.assertEqual(collection.imbalance, -50)

	def test_imbalance_blocks_submit(self):
		collection = self._make_collection(amount=200, expected_total=250)
		with self.assertRaises(ValidationError):
			collection.submit()

	def test_submit_increases_fund_balance(self):
		self._make_collection(amount=200).submit()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 200)

	def test_cancel_reverses_fund_balance(self):
		collection = self._make_collection(amount=200)
		collection.submit()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 200)
		collection.cancel()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 0)
