# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.patches.after_install import get_searched_doctypes
from churchit.patches.v1_0 import put_functions_before_songs_in_search as patch
from churchit.tests.helpers import RollbackEachTest

FILTER_BUTTONS = 5


class TestPutFunctionsBeforeSongsInSearch(RollbackEachTest):
	"""The search dialog's filter buttons take the shipped order only when nobody moved the rows."""

	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.cache.hdel, "global_search", "search_priorities")

	def set_listed(self, doctypes):
		settings = frappe.get_single("Global Search Settings")
		settings.allowed_in_global_search = []
		for doctype in doctypes:
			settings.append("allowed_in_global_search", {"document_type": doctype})
		settings.save()

	def get_listed(self):
		return frappe.get_all(
			"Global Search DocType",
			filters={"parent": "Global Search Settings"},
			pluck="document_type",
			order_by="idx",
		)

	def test_function_is_a_filter_button_and_song_is_not(self):
		self.assertIn("Function", get_searched_doctypes()[:FILTER_BUTTONS])
		self.assertNotIn("Song", get_searched_doctypes()[:FILTER_BUTTONS])

	def test_the_previous_shipped_order_becomes_the_new_one(self):
		self.set_listed([*patch.PREVIOUS_ORDER, "Ministry", "Contact"])

		patch.execute()
		patch.execute()

		self.assertEqual(
			self.get_listed(),
			["Person", "Family", "Group", "Sermon", "Function", "Song", "Ministry", "Contact"],
		)

	def test_an_order_someone_chose_stays(self):
		chosen = ["Person", "Song", "Family", "Group", "Sermon", "Function"]
		self.set_listed(chosen)

		patch.execute()

		self.assertEqual(self.get_listed(), chosen)
