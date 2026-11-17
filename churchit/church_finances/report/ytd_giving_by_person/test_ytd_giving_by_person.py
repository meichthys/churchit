# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_finances.doctype.payment_type.payment_type import create_non_cash_payment_type
from churchit.church_finances.report.first_time_givers.test_first_time_givers import give
from churchit.church_finances.report.person_donations.person_donations import get_columns
from churchit.church_finances.report.ytd_giving_by_person import ytd_giving_by_person
from churchit.church_finances.report.ytd_giving_by_person.ytd_giving_by_person import get_total_row
from churchit.tests.helpers import RollbackEachTest, ensure, make_person, make_two_churches


class TestYtdGivingByPerson(FrappeTestCase):
	def test_total_row_averages_over_all_gifts_not_over_the_averages(self):
		rows = [
			{"gift_count": 2, "ytd_amount": 100, "last_gift_date": "2026-01-05", "prior_year_amount": 10},
			{"gift_count": 3, "ytd_amount": 1030, "last_gift_date": "2026-03-01", "prior_year_amount": None},
		]

		total = get_total_row(rows)

		self.assertEqual(total["gift_count"], 5)
		self.assertEqual(total["ytd_amount"], 1130)
		self.assertEqual(total["avg_gift"], 226)
		self.assertEqual(total["last_gift_date"], "2026-03-01")
		self.assertEqual(total["prior_year_amount"], 10)

	def test_total_row_leaves_prior_year_empty_when_no_one_gave_last_year(self):
		rows = [
			{"gift_count": 1, "ytd_amount": 50, "last_gift_date": "2026-01-05", "prior_year_amount": None}
		]

		self.assertIsNone(get_total_row(rows)["prior_year_amount"])

	def test_person_donations_names_the_giver_unless_one_person_is_picked(self):
		self.assertIn("person", [column["fieldname"] for column in get_columns({})])
		self.assertNotIn("person", [column["fieldname"] for column in get_columns({"person": "PRSN-1"})])


class TestYtdGivingByPersonGifts(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.general = ensure("Fund", {"fund": "_Test YTD General"})
		cls.building = ensure("Fund", {"fund": "_Test YTD Building"})
		cls.cash = ensure("Payment Type", {"type": "Cash"})
		cls.check = ensure("Payment Type", {"type": "Check"})

	def row(self, person, amount, payment_type=None, check_number=None, fund=None):
		return {
			"person": person,
			"fund": fund or self.general,
			"payment_type": payment_type or self.cash,
			"amount": amount,
			"check_number": check_number,
		}

	def test_a_check_split_across_funds_is_one_gift(self):
		giver = make_person("_Test YTD", "Split").name
		give(
			"2032-01-01 00:00:00",
			[
				self.row(giver, 100, self.check, "1001"),
				self.row(giver, 500, self.check, "1001", self.building),
				self.row(giver, 40),
			],
		)
		give("2032-06-01 10:00:00", [self.row(giver, 60, self.check, "1002")])

		row = next(row for row in ytd_giving_by_person.execute({"year": 2032})[1] if row["person"] == giver)

		self.assertEqual(row["gift_count"], 3)
		self.assertEqual(row["ytd_amount"], 700)
		self.assertAlmostEqual(float(row["avg_gift"]), 700 / 3)

	def test_the_year_runs_from_new_years_day_to_the_last_minute_of_the_year(self):
		giver = make_person("_Test YTD", "Boundary").name
		new_giver = make_person("_Test YTD", "New").name
		give("2031-06-01 10:00:00", [self.row(giver, 25)])
		give("2031-12-31 23:59:00", [self.row(giver, 5)])
		give("2032-01-01 00:00:00", [self.row(giver, 10), self.row(new_giver, 15)])
		give("2032-12-31 23:59:00", [self.row(giver, 20)])
		give("2033-01-01 00:00:00", [self.row(giver, 1000)])

		rows = {row["person"]: row for row in ytd_giving_by_person.execute({"year": 2032})[1]}

		self.assertEqual(rows[giver]["ytd_amount"], 30)
		self.assertEqual(rows[giver]["prior_year_amount"], 30)
		self.assertEqual(str(rows[giver]["last_gift_date"]), "2032-12-31 23:59:00")
		self.assertIsNone(rows[new_giver]["prior_year_amount"])

	def test_property_given_last_year_is_no_prior_year_gift(self):
		create_non_cash_payment_type()
		giver = make_person("_Test YTD", "Property").name
		non_cash = frappe.db.get_value("Payment Type", {"is_non_cash": 1})
		give("2031-05-01 10:00:00", [{**self.row(giver, 0, non_cash), "description": "_Test piano"}])
		give("2032-05-01 10:00:00", [self.row(giver, 20)])

		row = next(row for row in ytd_giving_by_person.execute({"year": 2032})[1] if row["person"] == giver)

		self.assertIsNone(row["prior_year_amount"])


class TestYtdGivingByPersonChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def test_prior_year_counts_only_the_churches_the_report_shows(self):
		giver = make_person("_Test YTD", "Two Churches").name
		row = {
			"person": giver,
			"fund": ensure(
				"Fund", {"fund": "_Test YTD Shared"}, {"fund": "_Test YTD Shared", "is_shared": 1}
			),
			"payment_type": ensure("Payment Type", {"type": "Cash"}),
		}
		give("2032-03-01 10:00:00", [{**row, "amount": 10}], church=self.branch_a)
		give("2031-03-01 10:00:00", [{**row, "amount": 7}], church=self.branch_a)
		give("2031-04-01 10:00:00", [{**row, "amount": 99}], church=self.branch_b)

		_columns, rows = ytd_giving_by_person.execute({"year": 2032, "church": self.branch_a})

		self.assertEqual(next(r for r in rows if r["person"] == giver)["prior_year_amount"], 7)
