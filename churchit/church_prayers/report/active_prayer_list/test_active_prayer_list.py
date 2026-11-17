# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate

from churchit.church_prayers.report.active_prayer_list import active_prayer_list
from churchit.tests.helpers import RollbackEachTest, ensure

REPORT_DATE = "churchit.church_prayers.report.active_prayer_list.active_prayer_list.getdate"


class TestActivePrayerList(RollbackEachTest):
	def test_days_open_count_from_the_sites_date(self):
		request = frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": "_Test Days Open",
				"type": ensure("Prayer Request Type", {"type": "_Test Days Open"}),
				"visibility": "Whole Church",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Prayer Request", request.name, "creation", add_days(getdate(), -3))

		with patch(REPORT_DATE, return_value=add_days(getdate(), 7)):
			rows = {row.name: row.days_open for row in active_prayer_list.execute({})[1]}

		self.assertEqual(rows[request.name], 10)
