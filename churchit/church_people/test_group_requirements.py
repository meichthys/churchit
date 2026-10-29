# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from frappe.utils import add_days, getdate

from churchit.tests.helpers import RollbackEachTest, ensure, make_person

TRAINING = "_Test Group Safety Training"


class TestGroupRequirements(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.leader_role = ensure(
			"Group Role",
			{"role": "_Test Requirement Leader"},
			{"role": "_Test Requirement Leader", "is_leader": 1},
		)
		cls.member_role = ensure(
			"Group Role",
			{"role": "_Test Requirement Member"},
			{"role": "_Test Requirement Member", "is_leader": 0},
		)
		cls.training = ensure("Background Check Type", {"type": TRAINING})
		cls.uncleared = make_person("_Test Requirement", "Uncleared").name
		cls.cleared = make_person("_Test Requirement", "Cleared").name
		frappe.get_doc(
			{
				"doctype": "Background Check",
				"person": cls.cleared,
				"check_type": cls.training,
				"status": "Cleared",
				"completed_on": getdate(),
				"expires_on": add_days(getdate(), 365),
			}
		).insert(ignore_permissions=True)

	def make_group(self, members=(), **values):
		group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "_Test Requirement Group",
				"needs_background_check": 1,
				"required_checks": [{"check_type": self.training}],
				**values,
			}
		)
		for person, role in members:
			group.append("members", {"person": person, "group_role": role})
		return group.insert(ignore_permissions=True)

	def test_a_blocking_group_refuses_an_uncleared_leader(self):
		group = self.make_group(block_without_checks=1)
		group.append("members", {"person": self.uncleared, "group_role": self.leader_role})

		with self.assertRaisesRegex(frappe.ValidationError, f"is missing {TRAINING}"):
			group.save(ignore_permissions=True)

	def test_a_cleared_leader_joins_a_blocking_group(self):
		group = self.make_group(block_without_checks=1)
		group.append("members", {"person": self.cleared, "group_role": self.leader_role})
		group.save(ignore_permissions=True)

		self.assertEqual([row.person for row in group.reload().members], [self.cleared])

	def test_without_block_the_save_completes_with_a_warning(self):
		with mock.patch("frappe.msgprint") as msgprint:
			group = self.make_group(members=[(self.uncleared, self.leader_role)])

		self.assertEqual([row.person for row in group.reload().members], [self.uncleared])
		(problems,), _kwargs = msgprint.call_args
		self.assertTrue(any(f"is missing {TRAINING}" in problem for problem in problems), problems)

	def test_leaders_only_skips_a_member_row(self):
		group = self.make_group(block_without_checks=1, members=[(self.uncleared, self.member_role)])

		self.assertEqual(len(group.members), 1)

	def test_everyone_checks_a_member_row(self):
		with self.assertRaisesRegex(frappe.ValidationError, f"is missing {TRAINING}"):
			self.make_group(
				block_without_checks=1,
				checks_apply_to="Everyone",
				members=[(self.uncleared, self.member_role)],
			)

	def test_an_unchanged_row_is_not_checked_again(self):
		group = self.make_group(members=[(self.uncleared, self.leader_role)])
		group.block_without_checks = 1
		group.description = "Changed"
		group.save(ignore_permissions=True)

	def test_a_row_moved_into_a_leader_role_is_checked(self):
		group = self.make_group(block_without_checks=1, members=[(self.uncleared, self.member_role)])
		group.members[0].group_role = self.leader_role

		with self.assertRaisesRegex(frappe.ValidationError, f"is missing {TRAINING}"):
			group.save(ignore_permissions=True)

	def test_without_required_types_any_cleared_check_counts(self):
		group = self.make_group(block_without_checks=1, required_checks=[])
		group.append("members", {"person": self.uncleared, "group_role": self.leader_role})
		with self.assertRaisesRegex(frappe.ValidationError, "has none"):
			group.save(ignore_permissions=True)

		group.reload()
		group.append("members", {"person": self.cleared, "group_role": self.leader_role})
		group.save(ignore_permissions=True)

	def test_a_group_that_needs_no_checks_checks_nobody(self):
		group = self.make_group(
			needs_background_check=0, block_without_checks=1, members=[(self.uncleared, self.leader_role)]
		)

		self.assertEqual(len(group.members), 1)
