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
from frappe.utils import add_years, getdate

from churchit.church_people.report.person_birthdays_this_week import person_birthdays_this_week
from churchit.tests.helpers import ensure

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
