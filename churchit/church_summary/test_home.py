# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.desk.doctype.dock.dock import dock_key, get_app_dock
from frappe.website.utils import get_home_page

from churchit.church_summary.home import add_return_to_framework_dock, land_desk_users_on_summary
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

	def test_a_desk_user_who_cannot_open_summary_gets_none(self):
		# An ERPNext accountant on a shared site holds desk roles that Summary is not for.
		user = ensure_user("_test_home_other_app@example.com", "_Test Home", roles=("Website Manager",))
		self.assertEqual(frappe.db.get_value("User", user, "user_type"), "System User")
		self.assertFalse(default_workspace(user))

		land_desk_users_on_summary()

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

	def test_a_desk_user_without_one_still_opens_summary(self):
		user = ensure_user("_test_home_role@example.com", "_Test Home", roles=("Church Staff",))
		frappe.db.set_value("User", user, "default_workspace", None)

		frappe.set_user(user)
		try:
			self.assertEqual(get_home_page(), "desk/summary")
		finally:
			frappe.set_user("Administrator")


def framework_site_dock():
	name = frappe.db.get_value("Dock", {"app": "frappe", "standard": 0, "user": ""})
	return frappe.get_doc("Dock", name) if name else None


class TestReturnToChurchit(RollbackEachTest):
	def setUp(self):
		super().setUp()
		frappe.db.delete("Dock", {"app": "frappe", "standard": 0, "user": ""})

	def test_framework_rail_leads_back_to_summary_first(self):
		frappe.get_doc(
			{"doctype": "Dock", "app": "frappe", "items": [{"link_type": "Sidebar", "link_to": "Users"}]}
		).insert(ignore_permissions=True)

		add_return_to_framework_dock()
		add_return_to_framework_dock()

		rows = [row.link_to for row in framework_site_dock().items]
		self.assertEqual(rows[:2], ["Summary", "Users"])
		self.assertEqual(rows.count("Summary"), 1)

	def test_the_arrangement_keeps_every_framework_entry(self):
		add_return_to_framework_dock()

		named = {dock_key(row) for row in framework_site_dock().items}
		for entry in get_app_dock("frappe"):
			self.assertIn(dock_key(entry), named)

	def test_a_hidden_return_entry_stays_hidden(self):
		add_return_to_framework_dock()
		dock = framework_site_dock()
		dock.items[0].hidden = 1
		dock.save(ignore_permissions=True)

		add_return_to_framework_dock()

		self.assertEqual(framework_site_dock().items[0].hidden, 1)
