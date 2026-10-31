# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.desk.doctype.dock.dock import drop_dock_caches, get_app_dock

from churchit.patches.v1_0 import order_the_dock_by_weekly_use as patch
from churchit.tests.helpers import RollbackEachTest


class TestOrderTheDockByWeeklyUse(RollbackEachTest):
	"""A site's saved dock takes the shipped order only when nobody moved its rows."""

	def setUp(self):
		super().setUp()
		# Runs after the rollback, so no cached dock layer outlives its rows.
		self.addCleanup(drop_dock_caches, None)
		frappe.db.delete("Dock", {"app": "churchit", "standard": 0})

	def make_site_dock(self, order):
		items = [{"link_type": "Sidebar", "link_to": name, "hidden": name == "Missions"} for name in order]
		return frappe.get_doc({"doctype": "Dock", "app": "churchit", "items": items}).insert(
			ignore_permissions=True
		)

	def test_the_previous_shipped_order_becomes_the_new_one(self):
		dock = self.make_site_dock(patch.PREVIOUS_ORDER)

		patch.execute()

		dock.reload()
		self.assertEqual(
			[row.link_to for row in dock.items], [entry["link_to"] for entry in get_app_dock("churchit")]
		)
		self.assertEqual([row.link_to for row in dock.items if row.hidden], ["Missions"])

	def test_an_order_someone_chose_stays(self):
		chosen = list(reversed(patch.PREVIOUS_ORDER))
		dock = self.make_site_dock(chosen)

		patch.execute()

		dock.reload()
		self.assertEqual([row.link_to for row in dock.items], chosen)
