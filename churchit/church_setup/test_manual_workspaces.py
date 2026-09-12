# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_setup.manual_workspaces import hide_manual_desktop_icons


class TestManualWorkspaces(FrappeTestCase):
	def test_manual_desktop_icons_are_hidden(self):
		frappe.db.set_value("Desktop Icon", "Manual: Missions", "hidden", 0)

		hide_manual_desktop_icons()

		self.assertEqual(frappe.db.get_value("Desktop Icon", "Manual: Missions", "hidden"), 1)

	def test_leaves_non_manual_icons_alone(self):
		frappe.db.set_value("Desktop Icon", "Missions", "hidden", 0)

		hide_manual_desktop_icons()

		self.assertEqual(frappe.db.get_value("Desktop Icon", "Missions", "hidden"), 0)
