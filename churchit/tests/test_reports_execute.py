# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Every script report in the app runs with no filters and returns columns and rows.

The per-report tests cover their logic; this catches a report that no longer
imports, breaks on an empty filter dict, or returns a malformed shape.
"""

import importlib
import os

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_years, getdate, nowdate

from churchit.church_finances.dashboard_chart_source.finance_summary import finance_summary
from churchit.church_finances.report.donations import donations
from churchit.church_finances.report.donations_by_person import donations_by_person
from churchit.church_finances.report.expenses import expenses
from churchit.church_finances.report.income_statement import income_statement
from churchit.church_finances.report.person_donations import person_donations
from churchit.church_ministries.report.church_attendance import church_attendance
from churchit.church_ministries.report.function_attendance_by_person import function_attendance_by_person
from churchit.church_ministries.report.function_attendance_by_type import function_attendance_by_type
from churchit.church_people.report.person_birthdays_this_week import person_birthdays_this_week
from churchit.tests.helpers import ensure, make_function, make_person

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def report_modules():
	for root, _dirs, files in os.walk(APP_DIR):
		if os.path.basename(os.path.dirname(root)) != "report":
			continue
		stem = os.path.basename(root)
		if f"{stem}.py" in files:
			yield f"{os.path.relpath(root, os.path.dirname(APP_DIR)).replace(os.sep, '.')}.{stem}"


class TestReportsExecute(FrappeTestCase):
	def test_every_report_runs_with_empty_filters(self):
		modules = sorted(report_modules())
		self.assertGreater(len(modules), 30)
		failures = []
		for module_name in modules:
			try:
				result = importlib.import_module(module_name).execute({})
				columns, data = result[0], result[1]
				assert isinstance(columns, list) and columns, "no columns"
				assert isinstance(data, list), "data is not a list"
				assert all("fieldname" in column for column in columns), "column without fieldname"
			except Exception as exc:
				failures.append(f"{module_name}: {exc!r}")
		self.assertEqual(failures, [])


class TestBirthdaysThisWeekReport(FrappeTestCase):
	def test_birthdays_match_on_month_and_day_regardless_of_year(self):
		ensure("Life Event Type", {"type": "Birth"})
		person = frappe.get_doc({"doctype": "Person", "first_name": "_Test Weekly Birthday"})
		person.append("life_events", {"event_type": "Birth", "date": add_years(getdate(), -21)})
		person.insert(ignore_permissions=True)

		_columns, data = person_birthdays_this_week.execute({})
		self.assertIn(person.name, [row.name for row in data])


class TestDonationReports(FrappeTestCase):
	def make_submitted_collection(self, giver, amount):
		collection = frappe.get_doc({"doctype": "Collection", "date": nowdate(), "expected_total": amount})
		collection.append(
			"donations",
			{
				"payment_type": ensure("Payment Type", {"type": "Cash"}),
				"fund": ensure("Fund", {"fund": "_Test Report Fund"}),
				"amount": amount,
				"person": giver,
			},
		)
		collection.insert(ignore_permissions=True)
		collection.submit()
		return collection

	def test_cancelled_collections_are_left_out(self):
		giver = make_person("_Test Report Giver").name
		kept = self.make_submitted_collection(giver, 30)
		cancelled = self.make_submitted_collection(giver, 70)
		cancelled.cancel()

		listed = {row.name for row in donations.execute({})[1]}
		self.assertIn(kept.name, listed)
		self.assertNotIn(cancelled.name, listed)
		self.assertEqual(
			[row.collection for row in person_donations.execute({"person": giver})[1]], [kept.name]
		)
		totals = {row.person: row.total_amount for row in donations_by_person.execute({})[1]}
		self.assertEqual(totals[giver], 30)

	def test_drafts_are_left_out(self):
		giver = make_person("_Test Draft Giver").name
		kept = self.make_submitted_collection(giver, 30)
		draft = frappe.get_doc({"doctype": "Collection", "date": nowdate(), "expected_total": 70})
		draft.append("donations", {**kept.donations[0].as_dict(no_default_fields=True), "amount": 70})
		draft.insert(ignore_permissions=True)
		expense_type = ensure(
			"Expense Type",
			{"type": "_Test Draft Type"},
			{"type": "_Test Draft Type", "fund": kept.donations[0].fund},
		)
		draft_expense = frappe.get_doc(
			{"doctype": "Expense", "title": "_Test Draft Spend", "type": expense_type, "amount": 5}
		).insert(ignore_permissions=True)

		self.assertNotIn(draft.name, {row.name for row in donations.execute({})[1]})
		self.assertEqual(
			[row.collection for row in person_donations.execute({"person": giver})[1]], [kept.name]
		)
		totals = {row.person: row.total_amount for row in donations_by_person.execute({})[1]}
		self.assertEqual(totals[giver], 30)
		self.assertNotIn(draft_expense.name, {row.name for row in expenses.execute({})[1]})


class TestFinanceReportDates(FrappeTestCase):
	"""Collection and Expense dates carry a time, so the last day of a period runs to midnight."""

	def make_late_gift(self, date, amount):
		giver = make_person("_Test Late Giver").name
		fund = ensure("Fund", {"fund": "_Test Late Fund"})
		collection = frappe.get_doc({"doctype": "Collection", "date": date, "expected_total": amount})
		collection.append(
			"donations",
			{
				"payment_type": ensure("Payment Type", {"type": "Cash"}),
				"fund": fund,
				"amount": amount,
				"person": giver,
			},
		)
		collection.insert(ignore_permissions=True).submit()
		return giver, fund

	def test_a_gift_at_2359_on_the_last_day_counts_in_the_reports(self):
		giver, fund = self.make_late_gift("2031-03-31 23:59:00", 40)
		filters = {"from_date": "2031-03-01", "to_date": "2031-03-31"}

		totals = {row.person: row.total_amount for row in donations_by_person.execute(filters)[1]}
		self.assertEqual(totals.get(giver), 40)
		income = {row["fund"]: row["income"] for row in income_statement.execute(filters)[1]}
		self.assertEqual(income.get(fund), 40)

	def test_the_finance_summary_counts_a_gift_at_2359_in_its_month(self):
		def by_month():
			chart = finance_summary.get(
				timespan="Select Date Range",
				time_interval="Monthly",
				from_date="2031-05-01",
				to_date="2031-06-30",
			)
			return chart["datasets"][0]["values"]

		before = by_month()
		self.make_late_gift("2031-05-31 23:59:00", 25)
		after = by_month()

		self.assertEqual([a - b for a, b in zip(after, before, strict=True)], [25, 0])


class TestAttendanceReports(FrappeTestCase):
	def test_checked_in_people_count_as_attending(self):
		person = make_person("_Test Checked In").name
		function = make_function("_Test Checked In Service", start_date=nowdate())
		function.append("attendance", {"person": person, "attendance_type": "Checked-In"})
		function.save(ignore_permissions=True)

		self.assertIn(person, [row.person for row in church_attendance.execute({})[1]])
		by_person = function_attendance_by_person.execute({"person": person})[1]
		self.assertEqual([row.function for row in by_person], [function.name])
		by_type = {row.function: row.attendance_count for row in function_attendance_by_type.execute({})[1]}
		self.assertEqual(by_type.get(function.name), 1)
