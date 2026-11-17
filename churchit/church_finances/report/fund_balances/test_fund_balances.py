# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_finances.report.fund_balances import fund_balances
from churchit.tests.helpers import RollbackEachTest, ensure, make_two_churches

FUND_A = "_Test Balance A"
FUND_B = "_Test Balance B"


class TestFundBalances(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church_a, cls.church_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		ensure("Fund", {"fund": "_Test Balance A"}, {"fund": "_Test Balance A", "church": cls.church_a})
		ensure("Fund", {"fund": "_Test Balance B"}, {"fund": "_Test Balance B", "church": cls.church_b})

	def run_report(self, **filters):
		columns, data = fund_balances.execute(filters)
		return [column["fieldname"] for column in columns], {row.fund: row for row in data}

	def test_every_church_shows_each_fund_with_its_church(self):
		fieldnames, rows = self.run_report()

		self.assertIn("church", fieldnames)
		self.assertEqual(rows[FUND_A].church, self.church_a)
		self.assertEqual(rows[FUND_B].church, self.church_b)

	def test_one_picked_church_has_no_church_column(self):
		fieldnames, rows = self.run_report(church=self.church_a)

		self.assertNotIn("church", fieldnames)
		self.assertIn(FUND_A, rows)
		self.assertNotIn(FUND_B, rows)
