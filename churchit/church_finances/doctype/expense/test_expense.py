# Copyright (c) 2025, meichthys and Contributors
# See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestExpense(FrappeTestCase):
	def setUp(self):
		# Expense Type is a tree doctype whose inserts commit, so keep the Fund +
		# Expense Type as persistent fixtures and start each test from a zero balance.
		self.fund = _ensure("Fund", {"fund": "_Test Expense Fund"}, {"fund": "_Test Expense Fund"})
		self.expense_type = _ensure(
			"Expense Type",
			{"type": "_Test Expense Type"},
			{"type": "_Test Expense Type", "fund": self.fund},
		)
		fund = frappe.get_doc("Fund", self.fund)
		fund.transactions = []
		fund.save(ignore_permissions=True)
		frappe.db.commit()

	def _make_expense(self, amount=100, **values):
		return frappe.get_doc(
			{
				"doctype": "Expense",
				"title": "Test Expense",
				"amount": amount,
				"type": self.expense_type,
				**values,
			}
		).insert(ignore_permissions=True)

	def test_validate_sets_associated_fund_from_type(self):
		expense = self._make_expense()
		self.assertEqual(expense.associated_fund, self.fund)

	def test_submit_reduces_fund_balance(self):
		self._make_expense(amount=100).submit()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), -100)

	def test_cancel_restores_fund_balance(self):
		expense = self._make_expense(amount=100)
		expense.submit()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), -100)
		expense.cancel()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 0)

	def test_uncancelled_expense_cannot_be_deleted(self):
		expense = self._make_expense()
		with self.assertRaises(ValidationError):
			expense.delete()

	def test_cancelled_expense_can_be_deleted(self):
		expense = self._make_expense()
		expense.submit()
		expense.cancel()
		expense.delete()  # should not raise
		self.assertFalse(frappe.db.exists("Expense", expense.name))
