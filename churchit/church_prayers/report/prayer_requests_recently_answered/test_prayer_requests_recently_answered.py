# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, getdate

from churchit.church_prayers.report.prayer_requests_recently_answered.prayer_requests_recently_answered import (
	execute,
)
from churchit.tests.helpers import RollbackEachTest, ensure, make_person


class TestPrayerRequestsRecentlyAnswered(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.request_type = ensure("Prayer Request Type", {"type": "_Test Recently Answered"})
		ensure("Prayer Request Status", {"status": "Answered"})

	def answered(self, answered_on, asked_on=None, **values):
		request = frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": "_Test Recently Answered",
				"type": self.request_type,
				"status": "Answered",
				**values,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Prayer Request", request.name, "answered_on", answered_on)
		if asked_on:
			frappe.db.set_value("Prayer Request", request.name, "creation", asked_on)
		return request.name

	def test_lists_requests_by_the_day_they_were_answered(self):
		today = getdate()
		ann = make_person("Ann", "_Test Recently Answered")
		asked_long_ago = self.answered(
			add_days(today, -5), asked_on=add_days(today, -100), recipient_type="Person", recipient=ann.name
		)
		answered_today = self.answered(today)
		answered_long_ago = self.answered(add_days(today, -60))

		rows = [
			row
			for row in execute({"request_since": add_days(today, -30)})[1]
			if row.type == self.request_type
		]

		self.assertEqual([row.name for row in rows], [answered_today, asked_long_ago])
		self.assertNotIn(answered_long_ago, [row.name for row in rows])
		self.assertEqual((rows[1].answered_on, rows[1].recipient_name), (add_days(today, -5), ann.full_name))
