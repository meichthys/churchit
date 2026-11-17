# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate

from churchit.church_people.report.pastoral_care_watch_list import pastoral_care_watch_list
from churchit.tests.helpers import RollbackEachTest, ensure, make_person

REPORT_DATE = "churchit.church_people.report.pastoral_care_watch_list.pastoral_care_watch_list.getdate"


class TestPastoralCareWatchList(RollbackEachTest):
	def test_the_visit_window_counts_back_from_the_sites_date(self):
		person = make_person("_Test Watch", "Visit").name
		frappe.get_doc(
			{
				"doctype": "Visitation Log",
				"person": person,
				"visit_date": add_days(getdate(), -20),
				"visit_type": ensure("Visit Type", {"type": "_Test Watch Visit"}),
				"follow_up_needed": 1,
			}
		).insert(ignore_permissions=True)

		def listed():
			return {row["person"] for row in pastoral_care_watch_list.execute({"window_days": 30})[1]}

		self.assertIn(person, listed())
		with patch(REPORT_DATE, return_value=add_days(getdate(), 15)):
			self.assertNotIn(person, listed())
