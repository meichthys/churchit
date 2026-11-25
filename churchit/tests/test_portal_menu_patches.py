# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The patches that added the member pages to the portal menu."""

import frappe

from churchit.patches.v1_0 import add_household_and_directory_menu_items as menu_patch
from churchit.patches.v1_0 import rename_newsletter_subscription_menu_item
from churchit.tests.helpers import RollbackEachTest


class TestPortalMenuPatches(RollbackEachTest):
	def test_my_household_and_the_member_directory_are_added_once(self):
		frappe.db.delete(
			"Portal Menu Item", {"parent": "Portal Settings", "route": ("in", ("household", "directory"))}
		)
		frappe.db.set_single_value("People Settings", "member_directory", 0)

		menu_patch.execute()
		menu_patch.execute()

		rows = {
			row.route: row
			for row in frappe.get_single("Portal Settings").menu
			if row.route in ("household", "directory")
		}
		self.assertEqual(
			{route: (row.title, row.role, row.enabled) for route, row in rows.items()},
			{
				"household": ("My Household", "Church User", 1),
				"directory": ("Member Directory", "Church User", 0),
			},
		)


class TestPreferencesMenuItemPatch(RollbackEachTest):
	def test_the_newsletter_subscription_item_becomes_communication_preferences_once(self):
		routes = (rename_newsletter_subscription_menu_item.OLD_ROUTE, "preferences")
		frappe.db.delete("Portal Menu Item", {"parent": "Portal Settings", "route": ("in", routes)})
		# Inserted straight into the table: saving Portal Settings clears every cache, and the patch saves it once.
		frappe.get_doc(
			{
				"doctype": "Portal Menu Item",
				"parenttype": "Portal Settings",
				"parent": "Portal Settings",
				"parentfield": "menu",
				"idx": 99,
				"title": "Newsletter Subscription",
				"route": "newsletter-subscription",
				"reference_doctype": "Email Group Member",
				"role": "Church User",
				"enabled": 1,
			}
		).db_insert()

		rename_newsletter_subscription_menu_item.execute()
		rename_newsletter_subscription_menu_item.execute()

		menu = frappe.get_doc("Portal Settings").menu
		self.assertFalse([row for row in menu if row.route == "newsletter-subscription"])
		rows = [row for row in menu if row.route == "preferences"]
		self.assertEqual(
			[(row.title, row.role, row.enabled) for row in rows],
			[("Communication Preferences", "Church User", 1)],
		)
