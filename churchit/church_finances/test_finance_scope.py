# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Who owns the money once branches exist.

A Fund is a container and may be shared; every gift and every expense keeps the
church that gave or spent it. These pin both halves: a church cannot reach into
another church's fund, and the reports attribute a shared fund's money to the
church each row came from rather than to the fund's owner.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from churchit.church_finances.report.expenses import expenses as expenses_report
from churchit.church_finances.report.fund_balances import fund_balances
from churchit.church_finances.report.income_statement import income_statement
from churchit.church_scope import SHARED
from churchit.tests.helpers import (
	ensure,
	ensure_root_church,
	ensure_user,
	make_branch,
	make_person,
	set_multi_church,
)


def make_fund(name, church, **values):
	return frappe.get_doc({"doctype": "Fund", "fund": name, "church": church, **values}).insert(
		ignore_permissions=True
	)


def make_expense(title, expense_type, amount, **values):
	expense = frappe.get_doc(
		{
			"doctype": "Expense",
			"title": title,
			"type": expense_type,
			"amount": amount,
			"date": nowdate(),
			**values,
		}
	)
	expense.insert(ignore_permissions=True)
	return expense


def make_collection(fund, amount, **values):
	collection = frappe.get_doc(
		{"doctype": "Collection", "date": nowdate(), "expected_total": amount, **values}
	)
	payment_type = ensure("Payment Type", {"type": "Cash"})
	collection.append("donations", {"payment_type": payment_type, "fund": fund, "amount": amount})
	collection.insert(ignore_permissions=True)
	return collection


class TestFinanceChurchOwnership(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		set_multi_church(True)
		cls.branch = make_branch("_Test Money Branch", "TMB")
		frappe.db.set_value("Church", cls.branch, "publish", 1)
		cls.root_fund = make_fund("_Test Root Only Fund", cls.root)
		cls.shared_fund = make_fund("_Test Shared Fund", cls.root, is_shared=1)
		cls.branch_fund = make_fund("_Test Branch Only Fund", cls.branch)
		cls.root_type = cls.expense_type("_Test Root Fund Type", cls.root_fund.name)
		cls.shared_type = cls.expense_type("_Test Shared Fund Type", cls.shared_fund.name)
		cls.branch_manager = cls.bind_manager("_test_money_branch@example.com", "BranchMoney", cls.branch)
		cls.addClassCleanup(frappe.clear_cache)

	@classmethod
	def expense_type(cls, name, fund):
		"""An Expense Type is global: every church picks from the same list."""
		return ensure("Expense Type", {"type": name}, {"type": name, "fund": fund})

	@classmethod
	def bind_manager(cls, email, first_name, church):
		user = ensure_user(email, first_name, roles=("Church Manager",))
		make_person(first_name, "Manager", church=church, user=user)
		return user

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_a_shared_fund_belongs_to_no_single_church(self):
		self.assertEqual(frappe.db.get_value("Fund", self.shared_fund.name, "church"), SHARED)
		self.assertEqual(frappe.db.get_value("Fund", self.shared_fund.name, "shared_by_church"), self.root)

	def test_a_global_expense_type_cannot_debit_another_churchs_fund(self):
		"""The leak this closes: the type is shared by every church, the fund it names is not."""
		with self.assertRaises(frappe.PermissionError):
			make_expense("_Test Reaching Expense", self.root_type, 250, church=self.branch)

	def test_a_shared_fund_takes_every_churchs_spending(self):
		expense = make_expense("_Test Branch Expense", self.shared_type, 40, church=self.branch)
		expense.submit()

		self.assertEqual(expense.church, self.branch)
		self.assertEqual(expense.associated_fund, self.shared_fund.name)

	def test_a_collection_cannot_credit_another_churchs_fund(self):
		with self.assertRaises(frappe.PermissionError):
			make_collection(self.branch_fund.name, 10, church=self.root)

	def test_a_transfer_cannot_move_money_to_another_church(self):
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "Fund Transfer",
					"from_fund": self.branch_fund.name,
					"to_fund": self.root_fund.name,
					"amount": 5,
					"date": nowdate(),
					"church": self.branch,
				}
			).insert(ignore_permissions=True)

	def test_an_online_gift_keeps_the_church_of_the_page_it_came_from(self):
		"""A shared fund names no church, so the gift cannot take one from it."""
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(church=self.branch)
		try:
			gift = frappe.get_doc(
				{
					"doctype": "Online Donation",
					"amount": 30,
					"fund": self.shared_fund.name,
					"donor_name": "_Test Giver",
					"email": "_test_giver@example.com",
				}
			).insert(ignore_permissions=True)
		finally:
			frappe.local.form_dict = frappe._dict()

		self.assertEqual(gift.church, self.branch)

	def shared_fund_spending(self):
		"""What the income statement reports spent from the shared fund, as the current user."""
		rows = {row["fund"]: row["expense"] for row in income_statement.execute({})[1]}
		return rows.get(self.shared_fund.name, 0)

	def test_reports_attribute_a_shared_funds_money_to_the_church_it_came_from(self):
		"""Both churches spend from the one shared fund; each report shows only the reader's."""
		frappe.set_user(self.branch_manager)
		before = self.shared_fund_spending()
		frappe.set_user("Administrator")

		theirs = make_expense("_Test Root Share Expense", self.shared_type, 70, church=self.root)
		theirs.submit()
		mine = make_expense("_Test Branch Share Expense", self.shared_type, 11, church=self.branch)
		mine.submit()

		frappe.set_user(self.branch_manager)
		listed = [row.name for row in expenses_report.execute({})[1]]
		self.assertIn(mine.name, listed)
		self.assertNotIn(theirs.name, listed)
		self.assertEqual(
			self.shared_fund_spending() - before, 11, "the other church's spending reached this figure"
		)

	def test_a_shared_fund_shows_its_joint_balance_to_every_church(self):
		"""Sharing a fund shares the pot: the balance is the joint one, on purpose."""
		make_collection(self.shared_fund.name, 500, church=self.root).submit()

		frappe.set_user(self.branch_manager)
		balances = {row.fund: row.balance for row in fund_balances.execute({})[1]}
		self.assertIn("_Test Shared Fund", balances)
		self.assertNotIn("_Test Root Only Fund", balances)
