# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase


class TestFund(FrappeTestCase):
	def _make_fund(self, **values):
		fund = frappe.get_doc({"doctype": "Fund", "fund": "Test Goal Fund", **values})
		fund.append(
			"transactions",
			{"amount": 250, "source_type": "Donation", "source": "TEST-DONATION"},
		)
		# Skip Dynamic Link existence check — the math under test only needs the amount.
		fund.flags.ignore_links = True
		return fund.insert(ignore_permissions=True)

	def test_goal_progress_computed_from_balance(self):
		fund = self._make_fund(goal_amount=1000)
		# balance 250 / goal 1000 -> 25%
		self.assertEqual(fund.balance, 250)
		self.assertEqual(fund.goal_progress, 25)

	def test_goal_progress_zero_without_goal(self):
		fund = self._make_fund()
		self.assertEqual(fund.goal_progress, 0)

	def test_goal_progress_can_exceed_100_when_overfunded(self):
		fund = self._make_fund(goal_amount=100)
		# balance 250 / goal 100 -> 250%
		self.assertEqual(fund.goal_progress, 250)
