# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import make_function


class TestMinistry(FrappeTestCase):
	def _make_ministry(self, name, **values):
		return frappe.get_doc({"doctype": "Ministry", "ministry_name": name, **values}).insert(
			ignore_permissions=True
		)

	def test_end_date_cannot_precede_start_date(self):
		with self.assertRaises(ValidationError):
			self._make_ministry("_Test Backwards", start_date="2030-02-01", end_date="2030-01-01")

	def test_recurring_functions_lists_repeating_templates_only(self):
		ministry = self._make_ministry("_Test Recurring Ministry")
		template = make_function(
			"_Test Weekly Template",
			associated_ministry=ministry.name,
			auto_repeat=1,
			repeat_frequency="Weekly",
			repeat_day_of_week="Sunday",
		)
		make_function("_Test One-Off", associated_ministry=ministry.name)

		ministry.reload()
		ministry.run_method("onload")

		rows = {row.function: row.repeat_frequency for row in ministry.recurring_functions}
		self.assertEqual(rows, {template.name: "Weekly"})

	def test_recurring_functions_refreshed_on_save(self):
		ministry = self._make_ministry("_Test Refreshed Ministry")
		make_function(
			"_Test Daily Template",
			associated_ministry=ministry.name,
			auto_repeat=1,
			repeat_frequency="Daily",
		)
		ministry.reload()
		ministry.save(ignore_permissions=True)
		self.assertEqual(len(ministry.recurring_functions), 1)
