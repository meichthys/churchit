# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_finances.report.expenses import expenses
from churchit.tests.helpers import RollbackEachTest, ensure


def make_expense_type(name, fund):
	# Expense Type is a tree doctype, and its insert commits, so the types are made once for the class.
	return ensure("Expense Type", {"type": name}, {"type": name, "fund": fund})


class TestExpensesReport(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.fund_a = ensure("Fund", {"fund": "_Test Expenses Fund A"})
		cls.fund_b = ensure("Fund", {"fund": "_Test Expenses Fund B"})
		cls.type_a = make_expense_type("_Test Expenses Type A", cls.fund_a)
		cls.type_b = make_expense_type("_Test Expenses Type B", cls.fund_b)

	def spend(self, expense_type, amount, date):
		expense = frappe.get_doc(
			{
				"doctype": "Expense",
				"title": "_Test Spend",
				"type": expense_type,
				"amount": amount,
				"date": date,
			}
		).insert(ignore_permissions=True)
		return expense.submit()

	def test_a_date_range_runs_to_the_end_of_the_last_day_and_ends_with_a_total(self):
		early = self.spend(self.type_a, 10, "2032-02-29 23:59:00")
		inside = self.spend(self.type_a, 20, "2032-03-01 00:00:00")
		last = self.spend(self.type_b, 30, "2032-03-31 23:59:00")
		self.spend(self.type_b, 40, "2032-04-01 00:00:00")

		_columns, rows = expenses.execute({"from_date": "2032-03-01", "to_date": "2032-03-31"})

		self.assertEqual([row["name"] for row in rows[:-1]], [last.name, inside.name])
		self.assertNotIn(early.name, [row["name"] for row in rows])
		self.assertEqual(rows[-1]["amount"], 50)
		self.assertEqual(rows[-1]["is_total_row"], 1)

	def test_the_report_shows_how_and_when_an_expense_was_paid(self):
		paid = self.spend(self.type_a, 10, "2032-06-10 10:00:00")
		paid.db_set({"paid_on": "2032-06-12", "payment_reference": "Check 7"})
		unpaid = self.spend(self.type_a, 20, "2032-06-11 10:00:00")

		columns, rows = expenses.execute({"from_date": "2032-06-10", "to_date": "2032-06-11"})
		by_name = {row["name"]: row for row in rows[:-1]}

		self.assertIn("payment_reference", [column["fieldname"] for column in columns])
		self.assertEqual(
			(by_name[paid.name]["paid_on"].isoformat(), by_name[paid.name]["payment_reference"]),
			("2032-06-12", "Check 7"),
		)
		self.assertIsNone(by_name[unpaid.name]["paid_on"])

	def test_type_and_fund_filters(self):
		first = self.spend(self.type_a, 10, "2032-05-10 10:00:00")
		second = self.spend(self.type_b, 20, "2032-05-11 10:00:00")
		dates = {"from_date": "2032-05-01", "to_date": "2032-05-31"}

		_columns, by_type = expenses.execute({**dates, "type": self.type_a})
		_columns, by_fund = expenses.execute({**dates, "fund": self.fund_b})

		self.assertEqual([row["name"] for row in by_type[:-1]], [first.name])
		self.assertEqual([row["name"] for row in by_fund[:-1]], [second.name])

	def test_a_group_type_takes_in_the_types_beneath_it(self):
		group = ensure(
			"Expense Type",
			{"type": "_Test Expenses Group"},
			{"type": "_Test Expenses Group", "fund": self.fund_a, "is_group": 1},
		)
		child = ensure(
			"Expense Type",
			{"type": "_Test Expenses Child"},
			{"type": "_Test Expenses Child", "fund": self.fund_a, "parent_expense_type": group},
		)
		inside = self.spend(child, 15, "2032-06-10 10:00:00")
		self.spend(self.type_a, 10, "2032-06-11 10:00:00")

		_columns, rows = expenses.execute({"from_date": "2032-06-01", "to_date": "2032-06-30", "type": group})

		self.assertEqual([row["name"] for row in rows[:-1]], [inside.name])
		self.assertEqual(rows[-1]["amount"], 15)
