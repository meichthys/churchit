# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

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

	def tearDown(self):
		# setUp's commit() flushes whatever the previous test left uncommitted, so an
		# Expense created in a test body can otherwise persist permanently in the site
		# database. Cancel and delete explicitly rather than rely on rollback.
		for name in frappe.get_all("Expense", filters={"type": self.expense_type}, pluck="name"):
			if frappe.db.get_value("Expense", name, "docstatus") == 1:
				frappe.get_doc("Expense", name).cancel()
			frappe.db.delete("Expense", {"name": name})
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

	def test_submitted_expense_cannot_be_deleted(self):
		expense = self._make_expense()
		expense.submit()
		with self.assertRaises(ValidationError):
			expense.delete()

	def test_draft_expense_can_be_deleted(self):
		# A draft never reduced the fund, and cannot be cancelled, so blocking it
		# would leave it undeletable for good.
		expense = self._make_expense()
		expense.delete()
		self.assertFalse(frappe.db.exists("Expense", expense.name))

	def test_cancelled_expense_can_be_deleted(self):
		expense = self._make_expense()
		expense.submit()
		expense.cancel()
		expense.delete()  # should not raise
		self.assertFalse(frappe.db.exists("Expense", expense.name))
