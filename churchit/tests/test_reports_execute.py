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

from churchit.church_finances.report.donations import donations
from churchit.church_finances.report.donations_by_person import donations_by_person
from churchit.church_finances.report.person_donations import person_donations
from churchit.church_people.report.person_birthdays_this_week import person_birthdays_this_week
from churchit.tests.helpers import ensure, make_person

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
