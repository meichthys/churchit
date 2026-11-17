# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.desk.doctype.dock.dock import drop_dock_caches

from churchit.church_setup.doctype.church_features.test_church_features import dock_flags
from churchit.church_setup.doctype.church_features.user_dock import (
	get_empty_sidebars,
	sync_every_user,
	sync_user_dock,
	sync_user_on_roles_change,
)
from churchit.tests.helpers import RollbackEachTest, ensure_user

NARROW_ROLES = {
	"check_in": ("Church Check-In", "Inbox User"),
	"follow_up": ("Church Follow-up", "Inbox User"),
}


class TestUserDock(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.addCleanup(drop_dock_caches, None)

	def make_user(self, key, roles=None):
		return ensure_user(f"_test_dock_{key}@example.com", key, roles=roles or NARROW_ROLES[key])

	def test_a_follow_up_user_keeps_only_the_modules_with_a_page_for_them(self):
		user = self.make_user("follow_up")

		empty = get_empty_sidebars(user)

		self.assertTrue({"Summary", "Communications", "Foundations", "Settings"} <= empty)
		self.assertTrue({"People", "Help"}.isdisjoint(empty))

	def test_a_check_in_volunteer_keeps_ministries_and_people(self):
		user = self.make_user("check_in")

		empty = get_empty_sidebars(user)

		self.assertTrue({"Ministries", "People", "Help"}.isdisjoint(empty))
		self.assertIn("Communications", empty)

	def test_a_church_manager_hides_nothing(self):
		user = self.make_user("manager", roles=("Church Manager", "Workspace Manager"))

		self.assertEqual(get_empty_sidebars(user), set())
		sync_user_dock(user)
		self.assertEqual(dock_flags(user), {})

	def test_syncing_hides_the_empty_entries_in_the_users_own_layer(self):
		user = self.make_user("follow_up")

		sync_user_dock(user)

		flags = dock_flags(user)
		self.assertEqual({entry for entry, hidden in flags.items() if hidden}, get_empty_sidebars(user))
		self.assertEqual(flags["People"], 0)
		self.assertEqual(dock_flags().get("Summary", 0), 0, "the site's layer is not touched")

	def test_a_new_role_shows_the_entry_again(self):
		user = self.make_user("follow_up")
		sync_user_dock(user)

		doc = frappe.get_doc("User", user)
		doc.append("roles", {"role": "Church Staff"})
		doc.save(ignore_permissions=True)
		sync_user_on_roles_change(doc)

		self.assertEqual(dock_flags(user)["Communications"], 0)
		self.assertEqual(dock_flags(user)["Summary"], 0)

	def test_an_entry_the_user_hid_by_hand_stays_hidden(self):
		user = self.make_user("follow_up")
		sync_user_dock(user)
		dock = frappe.get_doc("Dock", {"app": "churchit", "standard": 0, "user": user})
		next(row for row in dock.items if row.link_to == "Help").hidden = 1
		dock.save(ignore_permissions=True)

		doc = frappe.get_doc("User", user)
		doc.append("roles", {"role": "Church Staff"})
		doc.save(ignore_permissions=True)
		sync_user_on_roles_change(doc)

		self.assertEqual(dock_flags(user)["Help"], 1)

	def test_a_module_that_church_features_hid_stays_hidden(self):
		user = self.make_user("follow_up")
		sync_user_dock(user)
		features = frappe.get_single("Church Features")
		features.enable_communications = 0
		features.save()

		doc = frappe.get_doc("User", user)
		doc.append("roles", {"role": "Church Staff"})
		doc.save(ignore_permissions=True)
		sync_user_on_roles_change(doc)

		self.assertEqual(dock_flags(user)["Communications"], 1)
		self.assertEqual(dock_flags(user)["Summary"], 0)

	def test_every_user_patch_runs_twice_without_change(self):
		user = self.make_user("check_in")

		sync_every_user()
		first = dock_flags(user)
		sync_every_user()

		self.assertEqual(dock_flags(user), first)
		self.assertEqual({entry for entry, hidden in first.items() if hidden}, get_empty_sidebars(user))
