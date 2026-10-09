# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_summary.home import land_desk_users_on_summary
from churchit.tests.helpers import RollbackEachTest, ensure_user


def default_workspace(user):
	return frappe.db.get_value("User", user, "default_workspace")


class TestLandOnSummary(RollbackEachTest):
	def test_a_new_desk_user_opens_summary(self):
		user = ensure_user("_test_home_desk@example.com", "_Test Home", roles=("Church Staff",))
		self.assertEqual(default_workspace(user), "Summary")

	def test_a_portal_member_gets_none(self):
		user = ensure_user("_test_home_member@example.com", "_Test Home")
		self.assertEqual(frappe.db.get_value("User", user, "user_type"), "Website User")
		self.assertFalse(default_workspace(user))

	def test_a_member_given_a_desk_role_opens_summary(self):
		user = ensure_user("_test_home_promoted@example.com", "_Test Home")
		frappe.get_doc("User", user).add_roles("Church Staff")
		self.assertEqual(default_workspace(user), "Summary")

	def test_a_desk_user_keeps_a_cleared_choice(self):
		user = ensure_user("_test_home_cleared@example.com", "_Test Home", roles=("Church Staff",))
		doc = frappe.get_doc("User", user)
		doc.default_workspace = None
		doc.save(ignore_permissions=True)
		self.assertFalse(default_workspace(user))

	def test_existing_desk_users_without_one_get_summary(self):
		unset = ensure_user("_test_home_unset@example.com", "_Test Home", roles=("Church Staff",))
		frappe.db.set_value("User", unset, "default_workspace", None)
		chosen = ensure_user("_test_home_chosen@example.com", "_Test Home", roles=("Church Staff",))
		frappe.db.set_value("User", chosen, "default_workspace", "People")

		land_desk_users_on_summary()

		self.assertEqual(default_workspace(unset), "Summary")
		self.assertEqual(default_workspace(chosen), "People")
