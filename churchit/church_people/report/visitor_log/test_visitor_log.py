# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate

from churchit.church_people.report.visitor_log import visitor_log
from churchit.tests.helpers import RollbackEachTest, make_function, make_person

REPORT_DATE = "churchit.church_people.report.visitor_log.visitor_log.getdate"


class TestVisitorLog(RollbackEachTest):
	def attend(self, person, start_date, attendance_type="Checked-In"):
		function = make_function("_Test Visitor Service", start_date=start_date)
		function.append("attendance", {"person": person, "attendance_type": attendance_type})
		return function.save(ignore_permissions=True).name

	def rows(self, **filters):
		return {row.name: row for row in visitor_log.execute(filters)[1]}

	def test_gives_each_visitor_their_first_counted_visit_and_visit_count(self):
		today = getdate()
		visitor = make_person("_Test Visitor", "Twice", membership="Visitor").name
		new = make_person("_Test Visitor", "New", membership="Visitor").name
		self.attend(visitor, add_days(today, -14), attendance_type="Signed-Up")
		first = self.attend(visitor, add_days(today, -7))
		self.attend(visitor, today)

		rows = self.rows()

		self.assertEqual(
			(rows[visitor].first_visit, rows[visitor].first_visit_date, rows[visitor].visit_count),
			(first, add_days(today, -7), 2),
		)
		self.assertEqual(
			(rows[new].first_visit, rows[new].first_visit_date, rows[new].visit_count), (None, None, 0)
		)

	def test_the_window_counts_back_from_the_sites_date(self):
		visitor = make_person("_Test Visitor", "Window", membership="Visitor").name
		frappe.db.set_value("Person", visitor, "creation", add_days(getdate(), -20))

		with patch(REPORT_DATE, return_value=add_days(getdate(), 50)):
			self.assertNotIn(visitor, self.rows(days=60))
		self.assertIn(visitor, self.rows(days=60))
