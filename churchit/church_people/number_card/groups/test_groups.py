# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.number_card.groups import groups
from churchit.tests.helpers import RollbackEachTest, ensure


class TestGroupsCard(RollbackEachTest):
	"""The People workspace's Active Groups card leaves Inactive groups out and opens the Active Groups list."""

	def test_counts_the_groups_that_are_not_inactive(self):
		ensure("Group Status", {"status": "Inactive"})
		before = groups.get_value()["value"]

		for status in ("Active", "Inactive"):
			frappe.get_doc(
				{"doctype": "Group", "group_name": f"_Test Groups Card {status}", "status": status}
			).insert(ignore_permissions=True)

		total = groups.get_value()
		self.assertEqual(total["value"], before + 1)
		self.assertEqual(total["route"], ["List", "Group", "Report", "Active Groups"])
