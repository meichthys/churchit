# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from contextlib import contextmanager

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_years, getdate, nowdate

from churchit.church_finances.doctype.budget.budget import (
	get_comparison_window,
	get_current_budget,
	get_window_scale,
)


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	doc = frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)
	# Expense Type is a tree doctype; inserting one commits internally and drops
	# the test's rollback savepoint. Only true the first time this fixture is
	# created, so only commit (and accept the loss of rollback protection) then.
	frappe.db.commit()
	return doc.name


class TestBudget(FrappeTestCase):
	def setUp(self):
		# Expense Type is a tree doctype whose inserts commit, so keep the fund and
		# types as persistent fixtures and clear their expenses before each test.
		self.fund = _ensure("Fund", {"fund": "_Test Budget Fund"}, {"fund": "_Test Budget Fund"})
		self.group_type = _ensure(
			"Expense Type",
			{"type": "_Test Budget Group"},
			{"type": "_Test Budget Group", "fund": self.fund, "is_group": 1},
		)
		self.child_type = _ensure(
			"Expense Type",
			{"type": "_Test Budget Child"},
			{"type": "_Test Budget Child", "fund": self.fund, "parent_expense_type": self.group_type},
		)
		self.other_type = _ensure(
			"Expense Type",
			{"type": "_Test Budget Other"},
			{"type": "_Test Budget Other", "fund": self.fund},
		)
		for expense_type in (self.group_type, self.child_type, self.other_type):
			frappe.db.delete("Expense", {"type": expense_type})
		fund = frappe.get_doc("Fund", self.fund)
		fund.transactions = []
		fund.save(ignore_permissions=True)
		self.budgets = []

	def tearDown(self):
		# Budgets this test created may have outlived the per-test rollback (see
		# _ensure), so delete them by name explicitly rather than rely on it.
		# Never delete unscoped: this site's real Budget data lives in this table too.
		if self.budgets:
			frappe.db.delete("Budget Line", {"parent": ("in", self.budgets)})
			frappe.db.delete("Budget", {"name": ("in", self.budgets)})
			frappe.db.commit()

	def _make_budget(self, start, end, lines=None):
		budget = frappe.get_doc({"doctype": "Budget", "start_date": start, "end_date": end})
		for expense_type, amount in lines or []:
			budget.append("lines", {"expense_type": expense_type, "budgeted_amount": amount})
		budget = budget.insert(ignore_permissions=True)
		self.budgets.append(budget.name)
		return budget

	def _make_expense(self, expense_type, amount, date=None, submit=True):
		expense = frappe.get_doc(
			{
				"doctype": "Expense",
				"title": "Test Budget Expense",
				"amount": amount,
				"type": expense_type,
				"date": date or nowdate(),
			}
		).insert(ignore_permissions=True)
		if submit:
			expense.submit()
		return expense

	def test_total_is_sum_of_lines(self):
		budget = self._make_budget(
			"2020-01-01", "2020-12-31", [(self.child_type, 400), (self.other_type, 600)]
		)
		self.assertEqual(budget.budgeted_amount, 1000)

	def test_end_date_before_start_date_is_rejected(self):
		with self.assertRaises(ValidationError):
			self._make_budget("2020-12-31", "2020-01-01")

	def test_duplicate_expense_type_is_rejected(self):
		with self.assertRaises(ValidationError):
			self._make_budget("2021-01-01", "2021-12-31", [(self.other_type, 100), (self.other_type, 200)])

	def test_actual_rolls_child_expense_types_into_the_group(self):
		self._make_expense(self.child_type, 250)
		budget = self._make_budget(
			add_days(nowdate(), -30), add_days(nowdate(), 30), [(self.group_type, 1000)]
		)
		row = budget.get_progress()["rows"][0]
		self.assertEqual(row["actual"], 250)
		self.assertEqual(row["variance"], 750)
		self.assertEqual(row["status"], "Under Budget")

	def test_draft_expenses_are_pending_not_actual(self):
		self._make_expense(self.other_type, 75, submit=False)
		budget = self._make_budget(
			add_days(nowdate(), -30), add_days(nowdate(), 30), [(self.other_type, 100)]
		)
		row = budget.get_progress()["rows"][0]
		self.assertEqual(row["actual"], 0)
		self.assertEqual(row["pending"], 75)

	def test_status_flags_overspending(self):
		self._make_expense(self.other_type, 150)
		budget = self._make_budget(
			add_days(nowdate(), -30), add_days(nowdate(), 30), [(self.other_type, 100)]
		)
		row = budget.get_progress()["rows"][0]
		self.assertEqual(row["status"], "Over Budget")
		self.assertEqual(row["pct"], 150)

	def test_expenses_outside_the_period_are_excluded(self):
		self._make_expense(self.other_type, 500, date=add_days(nowdate(), -90))
		budget = self._make_budget(
			add_days(nowdate(), -30), add_days(nowdate(), 30), [(self.other_type, 100)]
		)
		self.assertEqual(budget.get_progress()["rows"][0]["actual"], 0)

	def test_same_period_last_year_comparison_uses_prior_year_expenses(self):
		self._make_expense(self.other_type, 300, date=add_years(nowdate(), -1))
		budget = self._make_budget(
			add_days(nowdate(), -30), add_days(nowdate(), 30), [(self.other_type, 1000)]
		)
		row = budget.get_progress("Same Period Last Year")["rows"][0]
		self.assertEqual(row["comparison_actual"], 300)
		# The window is the same length as the period, so the budget is not scaled down.
		self.assertEqual(row["comparison_budget"], 1000)

	def test_current_budget_prefers_the_budget_covering_today(self):
		with self._other_budgets_hidden():
			self._make_budget(add_years(nowdate(), -3), add_years(nowdate(), -2))
			current = self._make_budget(add_days(nowdate(), -1), add_days(nowdate(), 1))
			self.assertEqual(get_current_budget(), current.name)

	def test_current_budget_falls_back_to_the_latest_budget(self):
		with self._other_budgets_hidden():
			self._make_budget(add_years(nowdate(), -3), add_years(nowdate(), -2))
			latest = self._make_budget(add_years(nowdate(), -2), add_years(nowdate(), -1))
			self.assertEqual(get_current_budget(), latest.name)

	@contextmanager
	def _other_budgets_hidden(self):
		"""get_current_budget() has no fixture scoping, so these tests need a Budget
		table with only their own rows. A savepoint hides real Budgets for the
		test body and restores them after, instead of deleting them outright."""
		frappe.db.savepoint("test_current_budget")
		try:
			frappe.db.delete("Budget")
			yield
		finally:
			frappe.db.rollback(save_point="test_current_budget")

	def test_window_scale_prorates_a_short_window_against_a_year(self):
		start, end = getdate("2026-01-01"), getdate("2026-12-31")
		window = (getdate("2026-01-01"), getdate("2026-01-31"))
		self.assertAlmostEqual(get_window_scale(window, start, end), 31 / 365)

	def test_last_quarter_window_is_the_previous_calendar_quarter(self):
		start, end = getdate("2026-01-01"), getdate("2026-12-31")
		window = get_comparison_window(start, end, "Last Quarter")
		quarter_start, quarter_end = window
		self.assertEqual(quarter_start.month % 3, 1)
		self.assertEqual(quarter_end.month % 3, 0)
		self.assertLess(quarter_end, getdate(nowdate()))

	def test_no_comparison_window_without_a_selection(self):
		self.assertIsNone(get_comparison_window(getdate("2026-01-01"), getdate("2026-12-31"), None))
