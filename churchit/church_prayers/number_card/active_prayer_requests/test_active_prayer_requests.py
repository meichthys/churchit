# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, now_datetime

from churchit.church_prayers.dashboard_chart_source.active_prayer_requests_by_type import (
	active_prayer_requests_by_type,
)
from churchit.church_prayers.number_card.active_prayer_requests import active_prayer_requests
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user


class TestActivePrayerRequestNumbers(RollbackEachTest):
	"""The Summary's Active Prayer Requests card and chart count one rule: open and not past the End Date."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.request_type = ensure("Prayer Request Type", {"type": "_Test Active Count"})
		ensure("Prayer Request Status", {"status": "Answered"})
		cls.praying = ensure_user(
			"_test_active_count_team@example.com", "_Test Team", roles=("Church Staff", "Church Prayer Team")
		)

	def make_request(self, **values):
		return frappe.get_doc(
			{"doctype": "Prayer Request", "title": "_Test Active Count", "type": self.request_type, **values}
		).insert(ignore_permissions=True)

	def numbers(self):
		chart = active_prayer_requests_by_type.get()
		by_type = dict(zip(chart["labels"], chart["datasets"][0]["values"], strict=True))
		return active_prayer_requests.get_value()["value"], by_type.get(self.request_type, 0)

	def test_ended_and_answered_requests_are_not_active(self):
		card, chart = self.numbers()
		self.make_request()
		self.make_request(end_date=add_days(now_datetime(), 3))
		self.make_request(end_date=add_days(now_datetime(), -3))
		self.make_request(status="Answered")

		self.assertEqual(self.numbers(), (card + 2, chart + 2))

	def test_the_prayer_team_counts_no_private_request_of_another_person(self):
		self.make_request(visibility="Private")
		self.make_request(visibility="Prayer Team")
		frappe.set_user(self.praying)

		self.assertEqual(self.numbers()[1], 1)

	def test_the_card_opens_the_active_prayer_requests_list(self):
		self.assertEqual(
			active_prayer_requests.get_value()["route"],
			["List", "Prayer Request", "Report", "Active Prayer Requests"],
		)
