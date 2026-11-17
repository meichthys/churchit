# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_missions.number_card.missionaries import missionaries
from churchit.tests.helpers import RollbackEachTest, ensure


class TestMissionariesCard(RollbackEachTest):
	"""The Missions workspace's Current Missionaries card counts the missionaries the Missions page lists."""

	def test_counts_every_missionary_but_the_inactive_ones(self):
		for status in ("Active", "Pending", "Inactive"):
			ensure("Missionary Status", {"status": status})
		before = missionaries.get_value()["value"]

		for status in ("Active", "Pending", "Inactive"):
			frappe.get_doc(
				{"doctype": "Missionary", "title": f"_Test Missionaries Card {status}", "status": status}
			).insert(ignore_permissions=True)

		total = missionaries.get_value()
		self.assertEqual(total["value"], before + 2)
		self.assertEqual(total["route"], ["List", "Missionary", "Report", "Current Missionaries"])
