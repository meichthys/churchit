# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.query_builder.functions import Coalesce, Sum
from frappe.utils import add_days

from churchit.church_finances.dashboard_chart_source.finance_summary import finance_summary
from churchit.church_finances.report.expenses.test_expenses import make_expense_type
from churchit.church_finances.report.first_time_givers.test_first_time_givers import give
from churchit.church_scope import scoped
from churchit.dashboard import time_buckets
from churchit.tests.helpers import RollbackEachTest, ensure

YEAR = {"timespan": "Select Date Range", "from_date": "2032-01-01", "to_date": "2032-12-31"}


def sum_in_range(doctype, amount_field, start, end):
	"""One bucket's sum, as the chart worked it out before it grouped by day."""
	table = frappe.qb.DocType(doctype)
	query = (
		frappe.qb.from_(table)
		.select(Coalesce(Sum(table[amount_field]), 0))
		.where((table.docstatus == 1) & (table.date >= start) & (table.date < add_days(end, 1)))
	)
	return float(scoped(query, table, {}).run()[0][0] or 0)


class TestFinanceSummary(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.fund = ensure("Fund", {"fund": "_Test Finance Summary Fund"})
		cls.expense_type = make_expense_type("_Test Finance Summary Type", cls.fund)

	def collect(self, date, amount):
		cash = ensure("Payment Type", {"type": "Cash"})
		give(date, [{"fund": self.fund, "payment_type": cash, "amount": amount}])

	def spend(self, date, amount):
		frappe.get_doc(
			{
				"doctype": "Expense",
				"title": "_Test Spend",
				"type": self.expense_type,
				"amount": amount,
				"date": date,
			}
		).insert(ignore_permissions=True).submit()

	def by_month(self):
		chart = finance_summary.get(**YEAR, time_interval="Monthly")
		return [dataset["values"][:3] for dataset in chart["datasets"]]

	def test_each_gift_and_expense_counts_in_its_own_month(self):
		before = self.by_month()
		self.collect("2032-01-31 23:59:00", 30)
		self.collect("2032-02-01 00:00:00", 20)
		self.collect("2032-03-31 12:00:00", 5)
		self.spend("2032-02-29 23:59:00", 7)

		after = self.by_month()

		changes = [
			[new - old for new, old in zip(*pair, strict=True)] for pair in zip(after, before, strict=True)
		]
		self.assertEqual(changes, [[30, 20, 5], [0, 7, 0]])

	def test_the_buckets_match_one_sum_for_each_bucket(self):
		self.collect("2032-01-31 23:59:00", 30)
		self.collect("2032-06-30 23:59:00", 11)
		self.spend("2032-07-01 00:00:00", 4)

		for interval in ("Daily", "Weekly", "Monthly", "Quarterly", "Yearly"):
			chart = finance_summary.get(**YEAR, time_interval=interval)
			buckets = time_buckets(YEAR["timespan"], interval, YEAR["from_date"], YEAR["to_date"])
			expected = [
				[sum_in_range(doctype, field, start, end) for start, end in buckets]
				for doctype, field in (("Collection", "total_amount"), ("Expense", "amount"))
			]
			self.assertEqual([dataset["values"] for dataset in chart["datasets"]], expected, interval)

	def test_an_empty_range_has_no_buckets(self):
		chart = finance_summary.get(
			timespan="Select Date Range",
			from_date="2032-02-01",
			to_date="2032-01-01",
			time_interval="Monthly",
		)

		self.assertEqual(chart["labels"], [])
		self.assertEqual([dataset["values"] for dataset in chart["datasets"]], [[], []])
