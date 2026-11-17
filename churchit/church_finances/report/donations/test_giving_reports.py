# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_finances.doctype.payment_type.payment_type import (
	NON_CASH,
	create_non_cash_payment_type,
)
from churchit.church_finances.report.collection_bank_reconciliation import (
	collection_bank_reconciliation as bank_reconciliation,
)
from churchit.church_finances.report.donations import donations
from churchit.church_finances.report.donations_by_person import donations_by_person
from churchit.church_finances.report.first_time_givers import first_time_givers
from churchit.church_finances.report.fund_transactions import fund_transactions
from churchit.church_finances.report.fund_transactions_by_date import fund_transactions_by_date
from churchit.church_finances.report.ytd_giving_by_person import ytd_giving_by_person
from churchit.tests.helpers import RollbackEachTest, ensure, make_person

CHECK = "_Test Report Check"


class TestGivingReports(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.first = make_person("_Test Report", "First").name
		cls.second = make_person("_Test Report", "Second").name
		cls.addClassCleanup(frappe.clear_cache)

	def make_gifts(self, date, rows):
		check = ensure("Payment Type", {"type": CHECK}, {"type": CHECK})
		fund_a = ensure("Fund", {"fund": "_Test Report Fund A"}, {"fund": "_Test Report Fund A"})
		fund_b = ensure("Fund", {"fund": "_Test Report Fund B"}, {"fund": "_Test Report Fund B"})
		funds = {"a": fund_a, "b": fund_b}
		collection = frappe.get_doc(
			{
				"doctype": "Collection",
				"date": date,
				"expected_total": sum(row["amount"] for row in rows),
				"donations": [
					{
						**row,
						"fund": funds[row.get("fund", "a")],
						"payment_type": row.get("payment_type", check),
					}
					for row in rows
				],
			}
		).insert(ignore_permissions=True)
		return collection.submit()

	def test_bank_reconciliation_keeps_two_givers_with_the_same_check_number_apart(self):
		collection = self.make_gifts(
			"2031-05-05",
			[
				{"person": self.first, "amount": 40, "check_number": "100"},
				{"person": self.second, "amount": 60, "fund": "b", "check_number": "100"},
			],
		)

		_columns, rows = bank_reconciliation.execute({"parent_filter": collection.name})

		self.assertEqual(
			sorted((row["person"], row["amount"]) for row in rows),
			sorted([(self.first, 40), (self.second, 60)]),
		)

	def test_bank_reconciliation_keeps_a_split_check_as_one_line_and_cash_by_fund(self):
		collection = self.make_gifts(
			"2031-05-06",
			[
				{"person": self.first, "amount": 30, "check_number": "200"},
				{"person": self.first, "amount": 20, "fund": "b", "check_number": "200"},
				{"person": self.first, "amount": 10, "payment_type": "Cash"},
				{"person": self.second, "amount": 5, "payment_type": "Cash"},
				{"person": self.second, "amount": 7, "fund": "b", "payment_type": "Cash"},
			],
		)

		columns, rows = bank_reconciliation.execute({"parent_filter": collection.name})

		check = next(row for row in rows if row["check_number"] == "200")
		self.assertEqual(check["amount"], 50)
		cash = {row["amount"]: row for row in rows if not row["check_number"]}
		self.assertEqual(sorted(cash), [7, 15])
		self.assertIsNone(cash[15]["person"])
		self.assertEqual(cash[7]["person"], self.second)
		self.assertEqual(next(c for c in columns if c["fieldname"] == "fund")["fieldtype"], "Link")

	def test_donations_filters_by_date_fund_and_person_and_ends_with_a_total(self):
		inside = self.make_gifts("2031-06-10", [{"person": self.first, "amount": 25}])
		self.make_gifts("2031-07-10", [{"person": self.second, "amount": 75, "fund": "b"}])
		filters = {"from_date": "2031-06-01", "to_date": "2031-06-30"}

		_columns, rows = donations.execute(filters)

		self.assertEqual([row["name"] for row in rows[:-1]], [inside.name])
		self.assertEqual(rows[0]["date"].isoformat()[:10], "2031-06-10")
		self.assertEqual(rows[-1]["amount"], 25)
		self.assertEqual(rows[-1]["is_total_row"], 1)
		_columns, by_person = donations.execute({**filters, "person": self.second})
		self.assertEqual(by_person, [])

	def test_donations_lists_the_newest_gift_date_first(self):
		# The older gift is entered last, so its collection is the last one modified.
		new = self.make_gifts("2031-08-20", [{"person": self.first, "amount": 2}])
		old = self.make_gifts("2031-08-01", [{"person": self.first, "amount": 1}])

		_columns, rows = donations.execute({"from_date": "2031-08-01", "to_date": "2031-08-31"})

		self.assertEqual([row["name"] for row in rows[:-1]], [new.name, old.name])

	def test_donations_by_person_ends_with_a_total(self):
		self.make_gifts(
			"2031-09-01",
			[{"person": self.first, "amount": 10}, {"person": self.second, "amount": 15}],
		)

		_columns, rows = donations_by_person.execute({"from_date": "2031-09-01", "to_date": "2031-09-30"})

		self.assertEqual(rows[-1]["total_amount"], 25)
		self.assertEqual(rows[-1]["is_total_row"], 1)

	def test_a_non_cash_gift_is_not_a_gift_in_the_year_report_or_for_first_time_givers(self):
		create_non_cash_payment_type()
		giver = make_person("_Test Report", "Piano").name
		self.make_gifts(
			f"{frappe.utils.nowdate()[:4]}-01-02",
			[{"person": giver, "amount": 0, "payment_type": NON_CASH, "description": "_Test piano"}],
		)

		_columns, ytd = ytd_giving_by_person.execute({})
		_columns, first_time = first_time_givers.execute({"window_days": 5000})

		self.assertNotIn(giver, [row["person"] for row in ytd])
		self.assertNotIn(giver, [row["person"] for row in first_time])

	def test_the_fund_ledger_names_the_record_behind_each_row(self):
		collection = self.make_gifts("2031-10-01", [{"person": self.first, "amount": 12}])
		filters = {"from_date": "2031-10-01", "to_date": "2031-10-31"}

		for report in (fund_transactions, fund_transactions_by_date):
			columns, rows = report.execute(filters)
			fieldnames = [column["fieldname"] for column in columns]
			self.assertIn("source_type", fieldnames)
			self.assertEqual(
				next(column for column in columns if column["fieldname"] == "source")["options"],
				"source_type",
			)
			self.assertIn(
				(collection.doctype, collection.name), [(r["source_type"], r["source"]) for r in rows]
			)
