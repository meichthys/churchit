# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe

from churchit.patches.v1_0 import clear_saved_sort_and_filters_of_people_and_shared_lists as patch
from churchit.tests.helpers import RollbackEachTest
from churchit.user_settings import clear_list_filters_and_sort

USER = "_test-saved-lists@example.com"
SAVED = {
	"last_view": "List",
	# An empty filter list also hides the list's default filter.
	"List": {"filters": [], "sort_by": "modified", "sort_order": "desc", "active_layout_name": "Mine"},
	"Report": {"filters": [["Family", "family_name", "like", "%Smith%"]], "fields": [["name", "Family"]]},
	"GridView": {"Email Address": [{"fieldname": "email", "columns": 4}]},
}


class TestClearListFiltersAndSort(RollbackEachTest):
	def save(self, doctype):
		frappe.db.sql(
			"insert into `__UserSettings` (`user`, `doctype`, `data`) values (%s, %s, %s)",
			(USER, doctype, json.dumps(SAVED)),
		)

	def get_saved(self, doctype):
		data = frappe.db.sql(
			"select `data` from `__UserSettings` where `user` = %s and `doctype` = %s", (USER, doctype)
		)
		return json.loads(data[0][0])

	def test_the_list_opens_on_its_own_filters_and_sort(self):
		self.save("Family")

		clear_list_filters_and_sort(("Family",))

		self.assertEqual(self.get_saved("Family")["List"], {"active_layout_name": "Mine"})

	def test_report_view_and_grid_columns_are_kept(self):
		self.save("Family")

		clear_list_filters_and_sort(("Family",))

		saved = self.get_saved("Family")
		for view in ("last_view", "Report", "GridView"):
			self.assertEqual(saved[view], SAVED[view], view)

	def test_other_lists_are_left_alone(self):
		self.save("Person")

		clear_list_filters_and_sort(("Family",))

		self.assertEqual(self.get_saved("Person"), SAVED)

	def test_settings_that_wait_in_redis_for_the_hourly_sync_are_cleared_too(self):
		key = f"Family::{USER}"
		frappe.cache.hset("_user_settings", key, json.dumps(SAVED))
		self.addCleanup(frappe.cache.hdel, "_user_settings", key)

		clear_list_filters_and_sort(("Family",))

		self.assertIsNone(frappe.cache.hget("_user_settings", key))
		saved = self.get_saved("Family")
		self.assertEqual(saved["List"], {"active_layout_name": "Mine"})
		self.assertEqual(saved["Report"], SAVED["Report"])

	def test_the_patch_names_only_doctypes_that_exist(self):
		self.assertEqual([name for name in patch.LISTS if not frappe.db.exists("DocType", name)], [])
