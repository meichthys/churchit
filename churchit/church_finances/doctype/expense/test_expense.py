# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, now, today

from churchit.church_finances.doctype.alms_request.alms_request import create_expense
from churchit.church_finances.doctype.fund.fund import add_transaction, format_amount
from churchit.tests.helpers import RollbackEachTest, make_person


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

	def test_an_amount_of_zero_or_less_is_refused(self):
		for amount in (0, -500):
			with self.assertRaisesRegex(ValidationError, "Enter the amount paid", msg=amount):
				self._make_expense(amount=amount)
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 0)

	def test_a_typed_date_far_ahead_warns_but_saves(self):
		expense = self._make_expense()
		expense.flags.ignore_permissions = False
		expense.date = f"{add_days(today(), 400)} 10:00:00"
		frappe.local.message_log = []
		expense.save()

		messages = [message["message"] for message in frappe.get_message_log()]
		self.assertTrue(any("more than 30 days after today" in message for message in messages), messages)

	def test_validate_sets_associated_fund_from_type(self):
		expense = self._make_expense()
		self.assertEqual(expense.associated_fund, self.fund)

	def test_submit_reduces_fund_balance(self):
		self._make_expense(amount=100).submit()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), -100)

	def test_paid_on_and_the_payment_reference_can_be_filled_in_after_submit(self):
		expense = self._make_expense(amount=100).submit()

		expense.db_set({"paid_on": "2032-01-15", "payment_reference": "Check 1042"})
		expense.reload()
		expense.paid_on = "2032-01-16"
		expense.save(ignore_permissions=True)

		self.assertEqual(
			frappe.db.get_value("Expense", expense.name, ["paid_on", "payment_reference"]),
			(getdate("2032-01-16"), "Check 1042"),
		)
		self.assertEqual(frappe.db.get_value("Expense", expense.name, "docstatus"), 1)

	def test_cancel_restores_fund_balance(self):
		expense = self._make_expense(amount=100)
		expense.submit()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), -100)
		expense.cancel()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 0)

	def test_submit_writes_one_ledger_row_without_saving_the_fund(self):
		versions = frappe.db.count("Version", {"ref_doctype": "Fund", "docname": self.fund})
		expense = self._make_expense(amount=100, notes="Hymnals")
		expense.submit()

		ledger = {"parent": self.fund, "source_type": "Expense", "source": expense.name}
		self.assertEqual(
			frappe.get_all("Financial Transaction", ledger, ["amount", "notes"]),
			[{"amount": -100, "notes": "Hymnals"}],
		)
		self.assertEqual(frappe.db.count("Version", {"ref_doctype": "Fund", "docname": self.fund}), versions)

		expense.cancel()
		self.assertFalse(frappe.db.exists("Financial Transaction", ledger))

	def test_cancel_restores_the_fund_charged_even_after_the_type_moves(self):
		expense = self._make_expense(amount=100)
		expense.submit()
		later_fund = frappe.get_doc({"doctype": "Fund", "fund": "_Test Later Fund"}).insert(
			ignore_permissions=True
		)
		frappe.db.set_value("Expense Type", self.expense_type, "fund", later_fund.name)
		try:
			expense.cancel()
			self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 0)
		finally:
			# setUp commits, so the type has to point back before the next test starts.
			frappe.db.set_value("Expense Type", self.expense_type, "fund", self.fund)
			frappe.delete_doc("Fund", later_fund.name, ignore_permissions=True, force=True)

	def test_saving_a_draft_warns_of_the_balance_it_would_leave(self):
		frappe.local.message_log = []
		self._make_expense(amount=100)

		[warning] = frappe.get_message_log()
		self.assertEqual(warning["indicator"], "orange")
		self.assertIn("Submitting this expense", warning["message"])
		self.assertIn(format_amount(-100), warning["message"])

	def test_the_approver_sees_the_negative_balance_on_submit(self):
		expense = self._make_expense(amount=100)
		frappe.local.message_log = []
		expense.submit()

		alert, warning = frappe.get_message_log()
		self.assertTrue(alert["alert"])
		self.assertIn(format_amount(100), alert["message"])
		self.assertNotIn("$", alert["message"].replace(format_amount(100), ""))
		self.assertEqual(warning["indicator"], "orange")
		self.assertIn(format_amount(-100), warning["message"])

	def test_an_expense_the_fund_can_pay_gives_no_warning(self):
		add_transaction(self.fund, 500, "Collection", "_TEST-GIFT", now())
		frappe.local.message_log = []
		self._make_expense(amount=100).submit()

		self.assertEqual([message.get("indicator") for message in frappe.get_message_log()], ["green"])

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


class TestAlmsExpenseCancel(RollbackEachTest):
	"""Cancelling the expense that paid an alms request lets the request get a corrected expense."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Expense Type inserts commit, so the type is made before any test's savepoint.
		fund = _ensure("Fund", {"fund": "_Test Expense Fund"}, {"fund": "_Test Expense Fund"})
		cls.expense_type = _ensure(
			"Expense Type", {"type": "_Test Expense Type"}, {"type": "_Test Expense Type", "fund": fund}
		)

	def setUp(self):
		super().setUp()
		person = make_person("_Test Alms", "Payee").name
		self.alms = frappe.get_doc(
			{
				"doctype": "Alms Request",
				"recipient_type": "Person",
				"recipient": person,
				"requestor": person,
				"description": "Rent",
				"status": "Approved",
				"amount": 100,
				"expense_type": self.expense_type,
			}
		).insert(ignore_permissions=True)

	def request(self):
		return frappe.db.get_value("Alms Request", self.alms.name, ["associated_expense", "status"])

	def test_cancelling_the_expense_approves_the_request_again(self):
		expense = frappe.get_doc("Expense", create_expense(self.alms.name))
		self.assertEqual(self.request(), (expense.name, "Distributed"))

		expense.cancel()
		self.assertEqual(self.request(), (expense.name, "Approved"))

		corrected = create_expense(self.alms.name)
		self.assertEqual(self.request(), (corrected, "Distributed"))

	def test_the_amended_expense_takes_over_the_request_so_it_is_paid_once(self):
		"""Frappe offers Amend after a cancel: the amended copy pays the request, not a second Create Expense."""
		expense = frappe.get_doc("Expense", create_expense(self.alms.name))
		expense.cancel()

		amended = frappe.copy_doc(expense)
		amended.update({"docstatus": 0, "amended_from": expense.name, "amount": 90})
		amended.insert()
		self.assertEqual(self.request(), (expense.name, "Approved"))
		amended.submit()

		self.assertEqual(self.request(), (amended.name, "Distributed"))
		with self.assertRaises(ValidationError):
			create_expense(self.alms.name)
