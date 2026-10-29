# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.summaries import refresh
from churchit.tests.helpers import RollbackEachTest, ensure, make_person


def make_group(group_name, people, **values):
	return frappe.get_doc(
		{"doctype": "Group", "group_name": group_name, "members": [{"person": p} for p in people], **values}
	).insert(ignore_permissions=True)


class TestGroupsSummary(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Member", "Groups").name

	def summary(self):
		refresh([self.person])
		person = frappe.get_doc("Person", self.person)
		return person.group_count, [row.group for row in person.groups]

	def test_groups_are_listed_by_name_and_counted(self):
		choir = make_group("_Test Zion Choir", [self.person]).name
		alpha = make_group("_Test Alpha Course", [self.person]).name

		self.assertEqual(self.summary(), (2, [alpha, choir]))

	def test_a_group_that_stopped_meeting_does_not_count(self):
		ensure("Group Status", {"status": "Inactive"})
		make_group("_Test Old Study", [self.person], status="Inactive")

		self.assertEqual(self.summary(), (0, []))

	def test_leaving_the_last_group_clears_the_list(self):
		group = make_group("_Test Leaving", [self.person])
		self.summary()
		group.members = []
		group.save(ignore_permissions=True)

		self.assertEqual(self.summary(), (0, []))
