# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.patches.after_install import create_group_types
from churchit.tests.helpers import RollbackEachTest, ensure


class TestGroupType(RollbackEachTest):
	def test_a_group_keeps_its_own_values_over_its_types_defaults(self):
		"""The desk copies a type's defaults into the form; the server copies nothing."""
		group_type = ensure(
			"Group Type",
			{"type": "_Test Open Type"},
			{
				"type": "_Test Open Type",
				"public": 1,
				"show_in_portal": 1,
				"requires_approval": 1,
				"capacity": 12,
			},
		)

		group = frappe.get_doc(
			{"doctype": "Group", "group_name": "_Test Typed Group", "group_type": group_type, "public": 0}
		).insert(ignore_permissions=True)

		group.reload()
		self.assertEqual((group.public, group.requires_approval, group.capacity), (0, 0, 0))

	def test_the_starter_types_are_seeded_once(self):
		frappe.db.delete("Group Type", {"type": "Class"})

		create_group_types()
		create_group_types()

		self.assertEqual(frappe.db.count("Group Type", {"type": "Class"}), 1)
		for group_type in ("Small Group", "Support Group", "Youth Group"):
			self.assertTrue(frappe.db.exists("Group Type", group_type))

	def test_seeding_leaves_a_churchs_edits_alone(self):
		create_group_types()
		frappe.db.set_value("Group Type", "Small Group", "public", 0)

		create_group_types()

		self.assertEqual(frappe.db.get_value("Group Type", "Small Group", "public"), 0)
