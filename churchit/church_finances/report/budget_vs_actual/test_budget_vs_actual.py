# Copyright (c) 2025, meichthys and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from churchit.church_finances.report.budget_vs_actual.budget_vs_actual import execute


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestBudgetVsActual(FrappeTestCase):
	def setUp(self):
		self.fund = _ensure("Fund", {"fund": "_Test Report Fund"}, {"fund": "_Test Report Fund"})
		self.expense_type = _ensure(
			"Expense Type",
			{"type": "_Test Report Expense Type"},
			{"type": "_Test Report Expense Type", "fund": self.fund},
		)
		frappe.db.commit()
		# Budget names are derived from their dates, so orphan lines left by a raw
		# delete would re-attach to the budget this test recreates.
		frappe.db.delete("Budget Line")
		frappe.db.delete("Budget")
		self.budget = frappe.get_doc(
			{
				"doctype": "Budget",
				"start_date": add_days(nowdate(), -30),
				"end_date": add_days(nowdate(), 30),
			}
		)
		self.budget.append("lines", {"expense_type": self.expense_type, "budgeted_amount": 500})
		self.budget.insert(ignore_permissions=True)

	def tearDown(self):
		# Budget's autoname is derived from real dates, so a fixture using
		# today +/- N days is indistinguishable from genuine data if it ever
		# outlives the test's rollback. Delete explicitly rather than rely on it.
		frappe.db.delete("Budget Line")
		frappe.db.delete("Budget")
		frappe.db.commit()

	def test_uses_the_current_budget_when_no_filter_is_given(self):
		columns, data, message = execute({})
		self.assertEqual(len(data), 1)
		self.assertEqual(data[0]["budgeted"], 500)
		self.assertIn(self.budget.name, message)

	def test_comparison_columns_appear_only_when_requested(self):
		columns, _data, _message = execute({"budget": self.budget.name})
		self.assertNotIn("comparison_actual", [column["fieldname"] for column in columns])

		columns, _data, _message = execute(
			{"budget": self.budget.name, "comparison": "Same Period Last Year"}
		)
		fieldnames = [column["fieldname"] for column in columns]
		self.assertIn("comparison_budget", fieldnames)
		self.assertIn("comparison_actual", fieldnames)
		self.assertIn("comparison_pct", fieldnames)

	def test_unknown_comparison_is_ignored(self):
		columns, _data, _message = execute({"budget": self.budget.name, "comparison": "Last Decade"})
		self.assertNotIn("comparison_actual", [column["fieldname"] for column in columns])

	def test_rolling_window_prorates_the_budgeted_amount(self):
		_columns, data, message = execute({"budget": self.budget.name, "comparison": "Last Month"})
		# A one-month window covers roughly half of a 61 day budget period.
		self.assertLess(data[0]["comparison_budget"], 500)
		self.assertGreater(data[0]["comparison_budget"], 0)
		self.assertIn("prorated", message)

	def test_empty_state_without_any_budget(self):
		frappe.db.delete("Budget")
		columns, data, message = execute({})
		self.assertEqual(data, [])
		self.assertTrue(columns)
		self.assertIn("No budget found", message)
