# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_ministries.report.function_count_by_type.function_count_by_type import execute
from churchit.tests.helpers import RollbackEachTest, ensure, make_function


class TestFunctionCountByType(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.function_type = ensure("Function Type", {"type": "_Test Count Type"})

	def make(self, start_date, **values):
		return make_function("_Test Count", start_date=start_date, type=self.function_type, **values)

	def count(self, **filters):
		rows = {row.type: row.counts for row in execute(filters)[1]}
		return rows.get(self.function_type, 0)

	def test_counts_the_functions_that_start_between_the_dates(self):
		self.make("2031-11-15")
		self.make("2031-11-15", end_date="2031-11-16")
		self.make("2031-12-06", end_date="2031-12-08")
		self.make("2032-01-10")

		self.assertEqual(self.count(start="2031-12-01", end="2031-12-31"), 1)
		self.assertEqual(self.count(start="2031-11-15", end="2031-11-15"), 2)
		self.assertEqual(self.count(start="2031-12-01"), 2)
		self.assertEqual(self.count(end="2031-11-30"), 2)
		self.assertEqual(self.count(), 4)

	def test_leaves_out_recurring_templates(self):
		template = self.make("2031-12-07")
		frappe.db.set_value("Function", template.name, "auto_repeat", 1)

		self.assertEqual(self.count(start="2031-12-01", end="2031-12-31"), 0)
