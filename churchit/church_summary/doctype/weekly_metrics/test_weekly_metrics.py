# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import get_first_day_of_week

from churchit.church_summary import metrics
from churchit.patches.v1_0 import set_weekly_metrics_titles
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_root_church,
	force_single_church,
	make_two_churches,
)

WEEK = get_first_day_of_week("2025-03-12")


def get_title(church):
	return frappe.db.get_value("Weekly Metrics", {"church": church, "week_start": WEEK}, "title")


class TestWeeklyMetricsTitleOneChurch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		force_single_church()
		cls.addClassCleanup(frappe.clear_cache)

	def test_a_row_is_titled_with_its_week(self):
		metrics.record_week(WEEK)

		self.assertEqual(get_title(self.root), str(WEEK))

	def test_the_patch_titles_a_row_written_before_titles(self):
		metrics.record_week(WEEK)
		frappe.db.set_value("Weekly Metrics", {"church": self.root, "week_start": WEEK}, "title", None)

		set_weekly_metrics_titles.execute()

		self.assertEqual(get_title(self.root), str(WEEK))


class TestWeeklyMetricsTitleTwoChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def test_each_churchs_row_of_a_week_names_its_church(self):
		metrics.record_week(WEEK)

		self.assertEqual(
			[get_title(self.branch_a), get_title(self.branch_b)],
			[f"{WEEK}, TSA", f"{WEEK}, TSB"],
		)
