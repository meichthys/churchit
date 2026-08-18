# Copyright (c) 2025, meichthys and Contributors
# See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_finances.doctype.alms_request.alms_request import create_expense


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestAlmsRequest(FrappeTestCase):
	def setUp(self):
		# Expense Type is a tree doctype whose inserts commit, so keep it and its
		# Fund as persistent fixtures rather than per-test records.
		self.fund = _ensure("Fund", {"fund": "_Test Alms Fund"}, {"fund": "_Test Alms Fund"})
		self.expense_type = _ensure(
			"Expense Type",
			{"type": "_Test Alms Expense Type"},
			{"type": "_Test Alms Expense Type", "fund": self.fund},
		)
		self.person = _ensure(
			"Person", {"first_name": "_Test Alms Recipient"}, {"first_name": "_Test Alms Recipient"}
		)

	def _make_request(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Alms Request",
				"recipient_type": "Person",
				"recipient": self.person,
				"requestor": self.person,
				"description": "Needs assistance",
				"status": "Approved",
				**values,
			}
		).insert(ignore_permissions=True)

	def test_title_combines_recipient_amount_and_status(self):
		alms = self._make_request(amount=250)
		self.assertIn("250", alms.title)
		self.assertIn("Approved", alms.title)

	def test_create_expense_requires_an_amount(self):
		alms = self._make_request(expense_type=self.expense_type)
		with self.assertRaises(ValidationError):
			create_expense(alms.name)

	def test_create_expense_requires_an_expense_type(self):
		alms = self._make_request(amount=100)
		with self.assertRaises(ValidationError):
			create_expense(alms.name)

	def test_create_expense_submits_expense_and_links_it_back(self):
		alms = self._make_request(amount=100, expense_type=self.expense_type)
		create_expense(alms.name)

		linked = frappe.db.get_value("Alms Request", alms.name, "associated_expense")
		self.assertTrue(linked)
		expense = frappe.get_doc("Expense", linked)
		self.assertEqual(expense.amount, 100)
		self.assertEqual(expense.type, self.expense_type)
		self.assertEqual(expense.docstatus, 1)

	def test_failed_create_expense_leaves_no_link(self):
		alms = self._make_request(amount=100)
		with self.assertRaises(ValidationError):
			create_expense(alms.name)
		self.assertFalse(frappe.db.get_value("Alms Request", alms.name, "associated_expense"))
