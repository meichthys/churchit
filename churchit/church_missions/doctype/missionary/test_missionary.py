# Copyright (c) 2025, meichthys and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from churchit.church_missions.doctype.missionary.missionary import create_missionary_expenses

TEST_FUND = "Test Missions Fund"
TEST_EXPENSE_TYPE = "Test Missionary Support"
TEST_PERSON_NAME = "Test Missionary Person"
TEST_MISSIONARY_TITLE = "Test Missionary"


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestMissionary(FrappeTestCase):
	def setUp(self):
		# Tree-doctype (Expense Type) inserts commit, so rollback can't fully isolate
		# these tests — clear any leftover missionary/expenses up front instead.
		for missionary in frappe.get_all(
			"Missionary", filters={"title": TEST_MISSIONARY_TITLE}, pluck="name"
		):
			frappe.db.delete("Expense", {"missionary": missionary})
			frappe.delete_doc("Missionary", missionary, force=True, ignore_permissions=True)

		fund = _ensure("Fund", {"fund": TEST_FUND}, {"fund": TEST_FUND})
		self.expense_type = _ensure(
			"Expense Type", {"type": TEST_EXPENSE_TYPE}, {"type": TEST_EXPENSE_TYPE, "fund": fund}
		)
		self.person = _ensure(
			"Person", {"first_name": TEST_PERSON_NAME}, {"first_name": TEST_PERSON_NAME}
		)

	def _make_missionary(self, **overrides):
		data = {
			"doctype": "Missionary",
			"title": TEST_MISSIONARY_TITLE,
			"person": self.person,
			"support_amount": 100,
			"support_frequency": "Monthly",
			"support_start_date": add_days(today(), -70),
			"auto_create_expenses": 1,
			"expense_type": self.expense_type,
		}
		data.update(overrides)
		return frappe.get_doc(data).insert(ignore_permissions=True)

	def test_auto_create_backfills_due_draft_expenses(self):
		missionary = self._make_missionary()
		create_missionary_expenses()

		expenses = frappe.get_all(
			"Expense",
			filters={"missionary": missionary.name},
			fields=["amount", "docstatus", "type"],
		)
		# Start 70 days ago, monthly -> 3 periods due on/before today.
		self.assertEqual(len(expenses), 3)
		for expense in expenses:
			self.assertEqual(expense.amount, 100)
			self.assertEqual(expense.docstatus, 0)  # left as draft for review
			self.assertEqual(expense.type, missionary.expense_type)

	def test_auto_create_is_idempotent(self):
		missionary = self._make_missionary()
		create_missionary_expenses()
		create_missionary_expenses()
		self.assertEqual(frappe.db.count("Expense", {"missionary": missionary.name}), 3)

	def test_auto_create_stops_after_support_end_date(self):
		missionary = self._make_missionary(support_end_date=add_days(today(), -40))
		create_missionary_expenses()
		# Only periods on/before the end date (start, +1 month) should exist.
		self.assertEqual(frappe.db.count("Expense", {"missionary": missionary.name}), 2)

	def test_disabled_missionary_creates_nothing(self):
		missionary = self._make_missionary(auto_create_expenses=0)
		create_missionary_expenses()
		self.assertEqual(frappe.db.count("Expense", {"missionary": missionary.name}), 0)

	def test_requires_positive_amount_when_enabled(self):
		from frappe.exceptions import ValidationError

		with self.assertRaises(ValidationError):
			self._make_missionary(support_amount=0)
