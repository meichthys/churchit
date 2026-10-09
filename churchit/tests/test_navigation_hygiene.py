# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Churchit dock and its module sidebars must agree, because the desk drops a mismatch silently.

A sidebar no dock entry names is reachable by URL only, and an entry naming no sidebar is left off
the rail. The desk opens a workspace in the first sidebar of the workspace's module, so a module
with two sidebars shows the wrong one, and a sidebar that opens on another module's workspace
switches away from itself on arrival.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestNavigationHygiene(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.sidebars = frappe.get_all(
			"Sidebar", filters={"app": "churchit", "standard": 1}, fields=["name", "module"]
		)

	def test_the_dock_names_every_sidebar_churchit_ships(self):
		docked = [row.link_to for row in frappe.get_doc("Dock", "churchit").items]
		self.assertEqual(sorted(docked), sorted(sidebar.name for sidebar in self.sidebars))

	def test_each_module_has_one_sidebar(self):
		modules = [sidebar.module for sidebar in self.sidebars]
		self.assertEqual(sorted({module for module in modules if modules.count(module) > 1}), [])

	def test_each_sidebar_opens_on_a_workspace_of_its_own_module(self):
		wrong = []
		for sidebar in self.sidebars:
			first = next(row for row in frappe.get_doc("Sidebar", sidebar.name).items if row.type == "Link")
			module = first.link_type == "Workspace" and frappe.db.get_value(
				"Workspace", first.link_to, "module"
			)
			if module != sidebar.module:
				wrong.append((sidebar.name, first.link_type, first.link_to))
		self.assertEqual(wrong, [])
