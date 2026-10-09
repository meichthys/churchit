# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.patches.v1_0 import add_step_in_law_and_cousin_relation_types as patch


class TestPersonRelationType(FrappeTestCase):
	def test_patch_adds_missing_types_and_keeps_existing_ones(self):
		frappe.db.delete("Person Relation Type", {"name": "Stepson"})
		frappe.db.set_value("Person Relation Type", "Cousin", "description", "Ours")

		patch.execute()
		patch.execute()

		self.assertTrue(frappe.db.exists("Person Relation Type", "Stepson"))
		self.assertEqual(frappe.db.get_value("Person Relation Type", "Cousin", "description"), "Ours")
